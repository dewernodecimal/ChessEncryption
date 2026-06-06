import chess
import chess.pgn
import chess.engine
import sys
import os
import time
import io
import shutil
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import queue

# Standard hardcoded path as fallback
STOCKFISH_PATH = r"C:\Users\vedug\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"

# Steganography ground rules
PIECES_FOR_ZERO = {chess.PAWN, chess.KNIGHT}
PIECES_FOR_ONE  = {chess.BISHOP, chess.ROOK, chess.QUEEN}
PIECE_FOR_SKIP  = chess.KING
OPENING_PLIES   = 6
ENGINE_THINK_TIME = 0.01

# Aesthetic Cyberpunk Color Scheme
BG_MAIN = "#0B0F19"
BG_PANEL = "#111827"
BORDER_COLOR = "#1F2937"
NEON_CYAN = "#00F0FF"
NEON_GREEN = "#39FF14"
TEXT_LIGHT = "#F3F4F6"
TEXT_DARK = "#9CA3AF"
BTN_START = "#059669"
BTN_PAUSE = "#D97706"
BTN_TERMINATE = "#DC2626"
BOARD_LIGHT = "#2C3540"
BOARD_DARK = "#1B1E23"

# Magic Verification Bytes
MAGIC_PREFIX = b"STEG"


def find_stockfish():
    """Robust utility to locate Stockfish binary across standard locations."""
    if os.path.exists(STOCKFISH_PATH):
        return STOCKFISH_PATH
    
    path_sf = shutil.which("stockfish")
    if path_sf:
        return path_sf
        
    path_sf_exe = shutil.which("stockfish.exe")
    if path_sf_exe:
        return path_sf_exe
        
    if os.path.exists("stockfish.exe"):
        return os.path.abspath("stockfish.exe")
        
    return ""


def sha256_ctr_crypt(data_bytes, password):
    """
    Symmetric SHA-256 CTR Stream Cipher.
    Generates key bytes by hashing (256-bit password key + 32-bit block index) and XORing.
    Highly secure and has 0 external dependencies.
    """
    key = hashlib.sha256(password.encode('utf-8')).digest()
    out = bytearray()
    
    for i, b in enumerate(data_bytes):
        block_counter = i // 32
        block_offset = i % 32
        if block_offset == 0:
            block_key = hashlib.sha256(key + block_counter.to_bytes(4, 'big')).digest()
        out.append(b ^ block_key[block_offset])
        
    return bytes(out)


def encrypt_payload(plaintext, password):
    """Encrypts plaintext string using the passcode, prepending magic verification bytes."""
    payload = MAGIC_PREFIX + plaintext.encode('utf-8')
    if not password:
        return payload
    return sha256_ctr_crypt(payload, password)


def decrypt_payload(ciphertext_bytes, password):
    """
    Decrypts bytes using the passcode.
    Returns (success_status, decrypted_string).
    """
    if not ciphertext_bytes:
        return False, ""
        
    if not password:
        decrypted = ciphertext_bytes
    else:
        decrypted = sha256_ctr_crypt(ciphertext_bytes, password)
        
    # Check if decryption was successful via the magic prefix
    if decrypted.startswith(MAGIC_PREFIX):
        try:
            msg_bytes = decrypted[len(MAGIC_PREFIX):]
            return True, msg_bytes.decode('utf-8')
        except Exception:
            return False, ""
    else:
        return False, ""


def bytes_to_bits(data_bytes):
    """Encodes standard bytes into a bit array (MSB first per byte)."""
    bits = []
    for byte in data_bytes:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits


def bits_to_bytes(bits):
    """Decodes a bit array back to a bytes object, processing complete bytes only."""
    if not bits:
        return b""
    bytes_list = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[i:i+8]:
            byte = (byte << 1) | bit
        bytes_list.append(byte)
    return bytes(bytes_list)


class EncoderControl:
    """Thread control flags for safe start/pause/terminate operations."""
    def __init__(self):
        self.is_paused = False
        self.is_stopped = False
        self.animation_speed = 0.1


class ThreadedStegoBot:
    def __init__(self, engine, gui_queue):
        self.engine = engine
        self.gui_queue = gui_queue

    def get_moves_grouped(self, board, target_bit):
        """Partition legal moves into matching piece types and king skips."""
        candidates = []
        skips = []
        for move in board.legal_moves:
            piece = board.piece_at(move.from_square)
            if piece is None:
                continue
            if piece.piece_type == PIECE_FOR_SKIP:
                skips.append(move)
            elif target_bit == 0 and piece.piece_type in PIECES_FOR_ZERO:
                candidates.append(move)
            elif target_bit == 1 and piece.piece_type in PIECES_FOR_ONE:
                candidates.append(move)
        return candidates, skips

    def pick_best_move(self, board, candidates):
        """Selects the best tactical move from the candidate moves."""
        if not candidates:
            return None
            
        if self.engine is not None:
            try:
                limit = chess.engine.Limit(time=ENGINE_THINK_TIME)
                analysis = self.engine.analyse(board, limit, multipv=3)
                best = None
                tactical_logs = []
                
                for idx, info in enumerate(analysis):
                    if "pv" in info and len(info["pv"]) > 0:
                        move = info["pv"][0]
                        score = info.get("score", None)
                        score_str = str(score.relative) if score else "N/A"
                        tactical_logs.append(f"PV#{idx+1}: {board.san(move)} ({score_str})")
                        
                        if best is None and move in candidates:
                            best = move
                            
                if tactical_logs:
                    log_to_gui(self.gui_queue, f"  [ENGINE] " + " | ".join(tactical_logs[:2]), 'info')
                    
                if best:
                    return best
            except Exception:
                pass
                
        # Heuristic fallback if Stockfish is missing
        best_candidate = candidates[0]
        max_score = -9999
        for move in candidates:
            score = 0
            if board.is_capture(move):
                score += 10
            if move.promotion:
                score += 20
            board.push(move)
            if board.is_check():
                score += 5
            board.pop()
            
            if score > max_score:
                max_score = score
                best_candidate = move
                
        if self.engine is None:
            log_to_gui(self.gui_queue, f"  [HEURISTIC] Chosen: {board.san(best_candidate)} (score: {max_score})", 'info')
            
        return best_candidate


def log_to_gui(gui_queue, text, level='default'):
    """Helper to send live logs to the scrolling green terminal GUI."""
    gui_queue.put({
        'type': 'log',
        'text': text,
        'level': level
    })


def make_thread_callback(gui_queue, control):
    """Factory to build an animation callback that respects pause/stop thread states."""
    def callback(board, move_desc, collected_bits, percent, game_num, tactics=""):
        gui_queue.put({
            'type': 'move',
            'fen': board.fen(),
            'desc': move_desc,
            'collected_bits': list(collected_bits),
            'percent': percent,
            'game_num': game_num,
            'tactics': tactics
        })
        
        while True:
            if control.is_stopped:
                raise InterruptedError("Stopped by user")
            if not control.is_paused:
                break
            time.sleep(0.05)
            
        elapsed = 0.0
        while elapsed < control.animation_speed:
            if control.is_stopped:
                raise InterruptedError("Stopped by user")
            time.sleep(0.05)
            elapsed += 0.05
            
    return callback


def encode_message_to_games_threaded(secret_message, password, bot, on_move_callback, gui_queue, control):
    """
    Multithreaded symmetric Chess Steganography & Encryption Encoder.
    Encrypts the plaintext first, then maps the encrypted bits into playable moves.
    """
    if password:
        log_to_gui(gui_queue, ">>> [CRYPT] Deriving SHA-256 key from passcode...", 'info')
        ciphertext_bytes = encrypt_payload(secret_message, password)
        log_to_gui(gui_queue, f">>> [CRYPT] SHA256-CTR encryption complete. Cipher bytes: {ciphertext_bytes.hex()[:32]}...", 'success')
    else:
        log_to_gui(gui_queue, ">>> [CRYPT] No passcode entered. Running in plain steganography mode.", 'warning')
        ciphertext_bytes = encrypt_payload(secret_message, "")
        
    data_bits = bytes_to_bits(ciphertext_bytes)
    bit_index = 0
    collected_bits = []
    games = []
    
    game_number = 1
    opening = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]
    
    log_to_gui(gui_queue, f">>> [STEGO] Bitstream compiled: {len(data_bits)} bits.", 'info')
    
    while bit_index < len(data_bits):
        if control.is_stopped:
            raise InterruptedError("Stopped")
            
        board = chess.Board()
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Steganography Stream"
        game.headers["Round"] = str(game_number)
        game.headers["White"] = "SmartStegoBot"
        game.headers["Black"] = "SmartStegoBot"
        
        log_to_gui(gui_queue, f"\n=== [GAME #{game_number}] Starting Rematch Board ===", 'success')
        log_to_gui(gui_queue, f">>> [GAME #{game_number}] Running opening book...", 'info')
        
        # Play the fixed opening
        node = game
        for san in opening:
            if control.is_stopped:
                raise InterruptedError("Stopped")
            move = board.parse_san(san)
            board.push(move)
            node = node.add_variation(move)
            
        on_move_callback(board, "Opening Play", collected_bits, (bit_index / len(data_bits)) * 100, game_number, "Opening active")
            
        # Main play loop for the current game
        while not board.is_game_over() and bit_index < len(data_bits):
            if control.is_stopped:
                raise InterruptedError("Stopped")
                
            current_bit = data_bits[bit_index]
            candidates, skips = bot.get_moves_grouped(board, current_bit)
            
            move = None
            desc = ""
            encoded = False
            
            if candidates:
                move = bot.pick_best_move(board, candidates)
                desc = f"Encoded Bit {current_bit}"
                encoded = True
            elif skips:
                move = bot.pick_best_move(board, skips)
                desc = "SKIP (King)"
            else:
                log_to_gui(gui_queue, f">>> [BLOCKED] No legal moves at ply {board.ply()}. Terminating game early...", 'warning')
                break
                
            san_move = board.san(move)
            board.push(move)
            node = node.add_variation(move)
            
            if encoded:
                collected_bits.append(current_bit)
                bit_index += 1
                log_to_gui(gui_queue, f"  [BIT] Encoded bit '{current_bit}' via move {san_move}", 'success')
            else:
                log_to_gui(gui_queue, f"  [SKIP] King move {san_move} played (Turn Bypassed)", 'info')
                
            on_move_callback(board, desc, collected_bits, (bit_index / len(data_bits)) * 100, game_number, f"Move: {san_move} ({desc})")
                
        games.append(game)
        
        # Game end or early block
        if bit_index < len(data_bits):
            reason = "Blocked" if not board.is_game_over() else ("Checkmate" if board.is_checkmate() else "Stalemate/Draw")
            log_to_gui(gui_queue, f">>> [GAME OVER] Reason: {reason}. Bypassing turns via board reset...", 'warning')
            gui_queue.put({
                'type': 'flash_game_over',
                'reason': reason
            })
            game_number += 1
            if getattr(control, "animation_speed", 0.1) > 0:
                time.sleep(1.5)
            
    return games


def run_encoder_thread(secret_message, password, engine_path, gui_queue, control):
    """Background worker thread executing encryption & steganography without blocking the GUI."""
    engine = None
    try:
        log_to_gui(gui_queue, ">>> [SYS] Booting Hybrid Chess Cryptography Console...", 'info')
        
        if engine_path and os.path.exists(engine_path):
            log_to_gui(gui_queue, f">>> [LOCATOR] Loading Stockfish from {os.path.basename(engine_path)}...", 'info')
            try:
                engine = chess.engine.SimpleEngine.popen_uci(engine_path)
                log_to_gui(gui_queue, ">>> [LOCATOR] Stockfish loaded! Multi-PV analysis enabled.", 'success')
            except Exception as e:
                log_to_gui(gui_queue, f">>> [WARNING] Stockfish loaded failed: {e}", 'warning')
                log_to_gui(gui_queue, ">>> [SYS] Defaulting to local Heuristic Engine.", 'warning')
        else:
            log_to_gui(gui_queue, ">>> [SYS] Stockfish not found. Defaulting to local Heuristic Engine.", 'warning')
            
        callback = make_thread_callback(gui_queue, control)
        bot = ThreadedStegoBot(engine, gui_queue)
        
        # Run encoding
        games = encode_message_to_games_threaded(secret_message, password, bot, callback, gui_queue, control)
        
        # Export all games as PGN
        pgn_exporter = io.StringIO()
        for game in games:
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
        pgn_data = pgn_exporter.getvalue()
        
        gui_queue.put({
            'type': 'complete',
            'pgn': pgn_data
        })
        
    except InterruptedError:
        log_to_gui(gui_queue, ">>> [SYS] Transmission halted by user.", 'warning')
    except Exception as e:
        log_to_gui(gui_queue, f">>> [FATAL] Stego system crash: {e}", 'error')
        gui_queue.put({'type': 'error', 'message': str(e)})
    finally:
        if engine:
            try:
                engine.quit()
            except Exception:
                pass


def decode_games_to_bytes(games_pgn_str):
    """Extracts raw encoded bits from the PGN games, returning raw ciphertext bytes."""
    pgn_io = io.StringIO(games_pgn_str)
    decoded_bits = []
    
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
            
        board = chess.Board()
        move_number = 0
        
        for move in game.mainline_moves():
            move_number += 1
            
            piece = board.piece_at(move.from_square)
            board.push(move)
            
            # Skip opening book
            if move_number <= OPENING_PLIES:
                continue
                
            if piece is None:
                continue
                
            if piece.piece_type == PIECE_FOR_SKIP:
                continue
            elif piece.piece_type in PIECES_FOR_ZERO:
                decoded_bits.append(0)
            elif piece.piece_type in PIECES_FOR_ONE:
                decoded_bits.append(1)
                
    return bits_to_bytes(decoded_bits)


def decode_games_to_text(games_pgn_str, password=""):
    """
    Symmetric Chess Steganography & Decryption Decoder.
    Extracts ciphertext from PGN and decrypts it with the passcode.
    """
    ciphertext_bytes = decode_games_to_bytes(games_pgn_str)
    success, decrypted_text = decrypt_payload(ciphertext_bytes, password)
    if success:
        return decrypted_text
    else:
        return "[Decryption failed: incorrect passcode]"


class CyberpunkStegoConsole:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🦾 Cyberpunk Chess Cryptography Console")
        self.root.geometry("1150x850")
        self.root.configure(bg=BG_MAIN)
        
        # Thread & queue controls
        self.gui_queue = queue.Queue()
        self.control = EncoderControl()
        self.worker_thread = None
        
        self.build_ui()
        self.check_queue()
        
    def build_ui(self):
        # 1. Main Header
        header_frame = tk.Frame(self.root, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, pady=10, padx=20)
        
        title_label = tk.Label(header_frame, text="⚡ HYBRID CHESS ENCRYPTION MODULE ⚡", 
                               font=("Courier New", 20, "bold"), bg=BG_MAIN, fg=NEON_CYAN)
        title_label.pack(side=tk.LEFT)
        
        self.round_label = tk.Label(header_frame, text="SYS IDLE", font=("Impact", 16), 
                                    bg=BG_MAIN, fg=NEON_GREEN)
        self.round_label.pack(side=tk.RIGHT)
        
        # 2. Main split view
        main_pane = tk.Frame(self.root, bg=BG_MAIN)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # Left Pane (Chess Board and Decrypted display)
        left_pane = tk.Frame(main_pane, bg=BG_MAIN, width=600)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Chess board frame
        self.board_frame = tk.Frame(left_pane, bg=BORDER_COLOR, bd=2)
        self.board_frame.pack(pady=5)
        
        self.squares = {}
        for row in range(8):
            for col in range(8):
                color = BOARD_LIGHT if (row + col) % 2 == 0 else BOARD_DARK
                label = tk.Label(self.board_frame, text=" ", font=("Segoe UI Symbol", 28),
                                 width=2, height=1, bg=color, fg="white")
                label.grid(row=row, column=col)
                self.squares[chess.square(col, 7-row)] = label
                
        # Status text below board
        self.info_label = tk.Label(left_pane, text="Awaiting Transmission Start...", font=("Consolas", 12), bg=BG_MAIN, fg="yellow")
        self.info_label.pack(pady=5)
        
        # Decrypted Stream Box
        decrypt_frame = tk.LabelFrame(left_pane, text=" 🔓 DECRYPTED RECIPIENT STREAM (LIVE AUTH CHECK) ", 
                                      font=("Consolas", 10, "bold"), bg=BG_PANEL, fg=NEON_GREEN, bd=1, relief=tk.SOLID)
        decrypt_frame.pack(fill=tk.X, pady=10, ipady=5)
        
        self.decoded_text_val = tk.StringVar(value='[Awaiting Decryption]')
        self.decoded_msg_label = tk.Label(decrypt_frame, textvariable=self.decoded_text_val, 
                                          font=("Courier New", 14, "bold"), bg=BG_PANEL, fg=NEON_GREEN, wraplength=550)
        self.decoded_msg_label.pack(pady=10)
        
        # Right Pane (Control panel and Live terminal log)
        right_pane = tk.Frame(main_pane, bg=BG_MAIN, width=500)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Control panel
        control_frame = tk.LabelFrame(right_pane, text=" ⚙️ CRYPTOGRAPHIC CONTROLS ", 
                                      font=("Consolas", 10, "bold"), bg=BG_PANEL, fg=NEON_CYAN, bd=1, relief=tk.SOLID)
        control_frame.pack(fill=tk.X, pady=5)
        
        # Message input
        tk.Label(control_frame, text="Secret Message:", font=("Consolas", 9), bg=BG_PANEL, fg=TEXT_DARK).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        self.msg_entry = tk.Entry(control_frame, width=42, font=("Consolas", 10), bg=BG_MAIN, fg=TEXT_LIGHT, insertbackground='white', bd=1, relief=tk.SOLID)
        self.msg_entry.grid(row=0, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.msg_entry.insert(0, "vedant vibhav mahi and neha ")
        
        # Stockfish path input
        tk.Label(control_frame, text="Stockfish Path:", font=("Consolas", 9), bg=BG_PANEL, fg=TEXT_DARK).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        self.sf_entry = tk.Entry(control_frame, width=32, font=("Consolas", 9), bg=BG_MAIN, fg=TEXT_LIGHT, insertbackground='white', bd=1, relief=tk.SOLID)
        self.sf_entry.grid(row=1, column=1, pady=5, sticky=tk.W)
        self.sf_entry.insert(0, find_stockfish())
        
        sf_btn = tk.Button(control_frame, text="Browse", font=("Consolas", 8), bg=BORDER_COLOR, fg=TEXT_LIGHT, relief=tk.SOLID, command=self.browse_sf)
        sf_btn.grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        
        # Passcode input
        tk.Label(control_frame, text="Security Key:", font=("Consolas", 9), bg=BG_PANEL, fg=TEXT_DARK).grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        self.pass_entry = tk.Entry(control_frame, width=42, font=("Consolas", 10), bg=BG_MAIN, fg=TEXT_LIGHT, show="*", insertbackground='white', bd=1, relief=tk.SOLID)
        self.pass_entry.grid(row=2, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.pass_entry.insert(0, "cyberpunk")
        
        # Delay slider
        tk.Label(control_frame, text="Pulse Delay (s):", font=("Consolas", 9), bg=BG_PANEL, fg=TEXT_DARK).grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        self.speed_slider = tk.Scale(control_frame, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL, bg=BG_PANEL, fg=NEON_CYAN, highlightthickness=0, troughcolor=BG_MAIN, activebackground=NEON_CYAN)
        self.speed_slider.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=5)
        self.speed_slider.set(0.15)
        
        # Buttons panel
        btn_frame = tk.Frame(control_frame, bg=BG_PANEL)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10, padx=10, sticky=tk.EW)
        
        self.start_btn = tk.Button(btn_frame, text="🚀 START TRANSMISSION", font=("Consolas", 10, "bold"), bg=BTN_START, fg="white", relief=tk.SOLID, width=22, command=self.on_start)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = tk.Button(btn_frame, text="⏸️ PAUSE", font=("Consolas", 10, "bold"), bg=BTN_PAUSE, fg="white", relief=tk.SOLID, width=11, state=tk.DISABLED, command=self.on_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(btn_frame, text="🛑 TERMINATE", font=("Consolas", 10, "bold"), bg=BTN_TERMINATE, fg="white", relief=tk.SOLID, width=12, state=tk.DISABLED, command=self.on_stop)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Tactical Log Live Terminal
        terminal_frame = tk.LabelFrame(right_pane, text=" 💾 CRYPTOGRAPHIC TRANSMISSION LOGS ", 
                                       font=("Consolas", 10, "bold"), bg=BG_PANEL, fg=NEON_CYAN, bd=1, relief=tk.SOLID)
        terminal_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable terminal text box
        self.terminal = tk.Text(terminal_frame, bg=BG_MAIN, fg=TEXT_LIGHT, font=("Consolas", 9), 
                                bd=0, highlightthickness=0, state=tk.DISABLED, wrap=tk.WORD)
        self.terminal.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)
        
        term_scrollbar = tk.Scrollbar(terminal_frame, command=self.terminal.yview, bg=BG_MAIN)
        term_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.terminal.config(yscrollcommand=term_scrollbar.set)
        
        # Terminal formatting color tags
        self.terminal.tag_config('info', foreground=NEON_CYAN)
        self.terminal.tag_config('success', foreground=NEON_GREEN)
        self.terminal.tag_config('warning', foreground="orange")
        self.terminal.tag_config('error', foreground="red")
        
        # Print initial boot message
        self.append_log(">>> [SYS] Console Ready. Type a message, passcode, and click START TRANSMISSION.")
        
    def append_log(self, text, level='default'):
        self.terminal.config(state=tk.NORMAL)
        self.terminal.insert(tk.END, text + "\n", level)
        self.terminal.see(tk.END)
        self.terminal.config(state=tk.DISABLED)
        
    def draw_board(self, board):
        piece_map = {'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
                     'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'}
        for sq in range(64):
            piece = board.piece_at(sq)
            if piece:
                txt = piece_map.get(piece.symbol(), "?")
                fg_color = "#FFFFFF" if piece.color == chess.WHITE else NEON_GREEN
                self.squares[sq].config(text=txt, fg=fg_color)
            else:
                self.squares[sq].config(text=" ")
                
    def browse_sf(self):
        path = filedialog.askopenfilename(
            title="Locate Stockfish Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if path:
            self.sf_entry.delete(0, tk.END)
            self.sf_entry.insert(0, path)
            
    def on_start(self):
        if self.worker_thread and self.control.is_paused:
            self.control.is_paused = False
            self.append_log(">>> [SYS] Transmission resumed.", 'success')
            self.start_btn.config(text="⚡ RESUMED", state=tk.DISABLED)
            self.pause_btn.config(state=tk.NORMAL)
            return
            
        message = self.msg_entry.get().strip()
        password = self.pass_entry.get().strip()
        
        if not message:
            messagebox.showerror("Error", "Please input a secret message to encrypt!")
            return
            
        self.control.is_stopped = False
        self.control.is_paused = False
        self.control.animation_speed = self.speed_slider.get()
        
        # Reset states
        self.round_label.config(text="SYS ACTIVE", fg=NEON_CYAN)
        self.decoded_text_val.set("")
        
        # Clear terminal log
        self.terminal.config(state=tk.NORMAL)
        self.terminal.delete(1.0, tk.END)
        self.terminal.config(state=tk.DISABLED)
        
        # Disable message input during transmission
        self.msg_entry.config(state=tk.DISABLED)
        self.sf_entry.config(state=tk.DISABLED)
        
        # Set button states
        self.start_btn.config(text="⚡ TRANSMITTING", state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL, text="⏸️ PAUSE")
        self.stop_btn.config(state=tk.NORMAL)
        
        # Spawn thread worker
        engine_path = self.sf_entry.get().strip()
        self.worker_thread = threading.Thread(
            target=run_encoder_thread,
            args=(message, password, engine_path, self.gui_queue, self.control),
            daemon=True
        )
        self.worker_thread.start()
        
    def on_pause(self):
        if self.control.is_paused:
            self.control.is_paused = False
            self.append_log(">>> [SYS] Transmission resumed.", 'success')
            self.pause_btn.config(text="⏸️ PAUSE")
            self.start_btn.config(text="⚡ TRANSMITTING", state=tk.DISABLED)
        else:
            self.control.is_paused = True
            self.append_log(">>> [SYS] Transmission paused. Click RESUME to continue.", 'warning')
            self.pause_btn.config(text="▶️ RESUME")
            self.start_btn.config(text="🚀 RESUME", state=tk.NORMAL)
            
    def on_stop(self):
        if self.worker_thread:
            self.control.is_stopped = True
            self.control.is_paused = False
            self.append_log(">>> [SYS] Sending TERMINATE signal to stego thread...", 'warning')
            self.root.after(200, self.cleanup_thread)
            
    def cleanup_thread(self):
        self.round_label.config(text="SYS TERMINATED", fg=BTN_TERMINATE)
        self.info_label.config(text="Transmission Aborted.", fg="red")
        
        self.start_btn.config(text="🚀 START TRANSMISSION", state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED, text="⏸️ PAUSE")
        self.stop_btn.config(state=tk.DISABLED)
        self.msg_entry.config(state=tk.NORMAL)
        self.sf_entry.config(state=tk.NORMAL)
        
        self.worker_thread = None
        
    def flash_game_over(self, reason):
        self.info_label.config(text=f"GAME OVER ({reason}) - RESETTING BOARD", fg="red")
        self.root.update()
        
    def check_queue(self):
        """Read updates from stego thread and refresh UI components in real-time."""
        self.control.animation_speed = self.speed_slider.get()
        
        try:
            while True:
                event = self.gui_queue.get_nowait()
                if event['type'] == 'move':
                    board = chess.Board(event['fen'])
                    self.draw_board(board)
                    
                    # Decryption Check
                    ciphertext_bytes = bits_to_bytes(event['collected_bits'])
                    current_pass = self.pass_entry.get().strip()
                    success, decrypted_msg = decrypt_payload(ciphertext_bytes, current_pass)
                    
                    if success:
                        self.decoded_text_val.set(f'"{decrypted_msg}"')
                        self.decoded_msg_label.config(fg=NEON_GREEN)
                    else:
                        self.decoded_text_val.set("❌ ACCESS DENIED / INCORRECT PASSCODE")
                        self.decoded_msg_label.config(fg="red")
                        
                    self.info_label.config(
                        text=f"Progress: {int(event['percent'])}% | {event['desc']}",
                        fg="yellow"
                    )
                    self.round_label.config(text=f"GAME #{event['game_num']}", fg=NEON_GREEN)
                    
                elif event['type'] == 'log':
                    self.append_log(event['text'], event['level'])
                    
                elif event['type'] == 'flash_game_over':
                    self.flash_game_over(event['reason'])
                    
                elif event['type'] == 'complete':
                    self.append_log("\n>>> [SYS] TRANSMISSION COMPLETE! All games saved to stego_games.pgn", 'success')
                    self.info_label.config(text="COMPLETE - ALL DATA TRANSMITTED", fg=NEON_GREEN)
                    self.round_label.config(text="COMPLETE", fg=NEON_GREEN)
                    
                    # Reset buttons
                    self.start_btn.config(text="🚀 START TRANSMISSION", state=tk.NORMAL)
                    self.pause_btn.config(state=tk.DISABLED)
                    self.stop_btn.config(state=tk.DISABLED)
                    self.msg_entry.config(state=tk.NORMAL)
                    self.sf_entry.config(state=tk.NORMAL)
                    
                    # Write final PGN file to disk
                    with open("stego_games.pgn", "w", encoding="utf-8") as f:
                        f.write(event['pgn'])
                        
                    current_pass = self.pass_entry.get().strip()
                    decoded = decode_games_to_text(event['pgn'], current_pass)
                    self.append_log(f">>> [DECRYPTOR] Extract verify decrypted: \"{decoded}\"", 'success')
                    
                elif event['type'] == 'error':
                    self.append_log(f"\n>>> [FATAL] Stego system failure: {event['message']}", 'error')
                    self.info_label.config(text="ERROR OCCURRED", fg="red")
                    self.cleanup_thread()
                    
                self.gui_queue.task_done()
        except queue.Empty:
            pass
            
        # Schedule check again in 50ms
        self.root.after(50, self.check_queue)


def test_encoder_decoder_roundtrip():
    print("=" * 60)
    print("RUNNING HYBRID ENCRYPTION SYMMETRIC VALIDATION TEST")
    print("=" * 60)
    
    test_cases = [
        ("Hello World!", "pass123"),
        ("vedant vibhav mahi and neha ", "cyberpunk"),
        ("Steganography is the practice of representing information within another message.", "securepassword"),
        ("Short", ""), # Test unencrypted fallback
        ("An extremely long test message with numbers 1234567890 & symbols #$@ to prove 100% byte encoding robustness!", "complex!@#pass")
    ]
    
    class DummyControl:
        is_stopped = False
        is_paused = False
        animation_speed = 0.0
        
    dummy_control = DummyControl()
    test_queue = queue.Queue()
    
    def dummy_callback(board, move_desc, collected_bits, percent, game_num, tactics=""):
        pass
        
    for msg, passcode in test_cases:
        print(f"Testing msg: '{msg}' | Passcode: '{passcode}'")
        
        bot = ThreadedStegoBot(engine=None, gui_queue=test_queue)
        games = encode_message_to_games_threaded(msg, passcode, bot, dummy_callback, test_queue, dummy_control)
        
        pgn_exporter = io.StringIO()
        for idx, game in enumerate(games):
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
            
        pgn_str = pgn_exporter.getvalue()
        
        # Test 1: Decryption with correct passcode (Must Pass)
        decoded_correct = decode_games_to_text(pgn_str, passcode)
        print(f"  Decoded Correct: '{decoded_correct}'")
        assert decoded_correct == msg, f"ERROR: Decrypted message does not match! Got '{decoded_correct}', expected '{msg}'"
        
        # Test 2: Decryption with incorrect passcode (Must Fail if passcode is not empty)
        if passcode:
            decoded_wrong = decode_games_to_text(pgn_str, "wrong_passcode")
            print(f"  Decoded Incorrect: '{decoded_wrong}'")
            assert "incorrect passcode" in decoded_wrong, f"ERROR: Decryption did not fail on wrong passcode!"
            
        print("  -> SUCCESS: Symmetric roundtrip validation passed!")
        
    print("=" * 60)
    print("ALL STEGANOGRAPHY & HYBRID ENCRYPTION TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_encoder_decoder_roundtrip()
        sys.exit(0)
        
    console = CyberpunkStegoConsole()
    console.root.mainloop()
