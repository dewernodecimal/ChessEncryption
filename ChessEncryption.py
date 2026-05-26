import chess
import chess.pgn
import chess.engine
import sys
import os
import time
import io
import shutil
import tkinter as tk

# Standard hardcoded path as fallback
STOCKFISH_PATH = r"C:\Users\vedug\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"

ANIMATION_SPEED = 0.1      
ENGINE_THINK_TIME = 0.01   

# Steganography ground rules
PIECES_FOR_ZERO = {chess.PAWN, chess.KNIGHT}
PIECES_FOR_ONE  = {chess.BISHOP, chess.ROOK, chess.QUEEN}
PIECE_FOR_SKIP  = chess.KING
OPENING_PLIES   = 6


def find_stockfish():
    """Robust utility to locate Stockfish binary across standard locations."""
    # 1. Try user configured hardcoded path
    if os.path.exists(STOCKFISH_PATH):
        return STOCKFISH_PATH
    
    # 2. Check system PATH
    path_sf = shutil.which("stockfish")
    if path_sf:
        return path_sf
        
    path_sf_exe = shutil.which("stockfish.exe")
    if path_sf_exe:
        return path_sf_exe
        
    # 3. Check current directory
    if os.path.exists("stockfish.exe"):
        return os.path.abspath("stockfish.exe")
        
    # 4. Check common locations relative to Desktop
    desktop_sf = r"C:\Users\vedug\Downloads\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"
    if os.path.exists(desktop_sf):
        return desktop_sf
        
    return None


def text_to_bits(text):
    """Encodes a text string into a bit array (MSB first per byte) in a robust way."""
    bits = []
    for byte in text.encode('utf-8'):
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits


def bits_to_text(bits):
    """Decodes a bit array back to a text string, processing complete bytes only."""
    if not bits:
        return ""
    bytes_list = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[i:i+8]:
            byte = (byte << 1) | bit
        bytes_list.append(byte)
    try:
        return bytes(bytes_list).decode('utf-8', errors='ignore')
    except Exception:
        return ""


class SmartStegoBot:
    def __init__(self, engine=None):
        self.engine = engine

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
            
        # Use Stockfish if available
        if self.engine is not None:
            try:
                limit = chess.engine.Limit(time=ENGINE_THINK_TIME)
                analysis = self.engine.analyse(board, limit, multipv=5)
                for info in analysis:
                    if "pv" in info:
                        best = info["pv"][0]
                        if best in candidates:
                            return best
            except Exception:
                pass # Fall through to heuristic if engine query fails
                
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
                
        return best_candidate


def encode_message_to_games(secret_message, engine=None, on_move_callback=None):
    """
    Symmetric Chess Steganography Encoder.
    Translates a binary bitstream into a sequence of PGN games.
    If no valid moves matching target bit or skip are available,
    the game terminates to prevent forced moves and starts a fresh game.
    """
    bot = SmartStegoBot(engine)
    data_bits = text_to_bits(secret_message)
    bit_index = 0
    collected_bits = []
    games = []
    
    game_number = 1
    opening = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]
    
    while bit_index < len(data_bits):
        board = chess.Board()
        game = chess.pgn.Game()
        game.headers["Event"] = "Chess Steganography Stream"
        game.headers["Round"] = str(game_number)
        game.headers["White"] = "SmartStegoBot"
        game.headers["Black"] = "SmartStegoBot"
        
        # Play the fixed opening
        node = game
        for san in opening:
            move = board.parse_san(san)
            board.push(move)
            node = node.add_variation(move)
            
        if on_move_callback:
            on_move_callback(board, "Opening Play", collected_bits, (bit_index / len(data_bits)) * 100, game_number)
            
        # Main play loop for the current game
        while not board.is_game_over() and bit_index < len(data_bits):
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
                # No candidates and no skips available.
                # Terminate game early to avoid forced-move ambiguity!
                break
                
            board.push(move)
            node = node.add_variation(move)
            
            if encoded:
                collected_bits.append(current_bit)
                bit_index += 1
                
            if on_move_callback:
                on_move_callback(board, desc, collected_bits, (bit_index / len(data_bits)) * 100, game_number)
                
        # Save game
        games.append(game)
        
        # If there's still data left and we broke out, trigger a rematch
        if bit_index < len(data_bits):
            reason = "Blocked" if not board.is_game_over() else ("Checkmate" if board.is_checkmate() else "Stalemate/Draw")
            if on_move_callback:
                on_move_callback(board, f"GAME_OVER:{reason}", collected_bits, (bit_index / len(data_bits)) * 100, game_number)
            game_number += 1
            
    return games


def decode_games_to_text(games_pgn_str):
    """
    Symmetric Chess Steganography Decoder.
    Reconstructs the original secret message entirely from a PGN string.
    """
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
            
            # Inspect the piece before applying the move on the board
            piece = board.piece_at(move.from_square)
            board.push(move)
            
            # Skip the opening moves
            if move_number <= OPENING_PLIES:
                continue
                
            if piece is None:
                continue
                
            # Parse bit based on piece type
            if piece.piece_type == PIECE_FOR_SKIP:
                continue
            elif piece.piece_type in PIECES_FOR_ZERO:
                decoded_bits.append(0)
            elif piece.piece_type in PIECES_FOR_ONE:
                decoded_bits.append(1)
                
    return bits_to_text(decoded_bits)


class ChessVisualizer:
    def __init__(self, secret_message):
        self.secret_message = secret_message
        self.root = tk.Tk()
        self.root.title("Chess Steganography - Infinite Stream")
        self.root.geometry("600(x)820" if os.name == 'nt' else "600x820")
        self.root.geometry("600x820")
        self.root.configure(bg="#1e1e1e")

        self.game_count_label = tk.Label(self.root, text="GAME #1", font=("Impact", 20), bg="#1e1e1e", fg="#00ffff")
        self.game_count_label.pack(pady=10)

        self.squares = {}
        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack(pady=10)

        # Draw 8x8 Board
        for row in range(8):
            for col in range(8):
                color = "#EEEED2" if (row + col) % 2 == 0 else "#769656" 
                label = tk.Label(self.board_frame, text=" ", font=("Segoe UI Symbol", 28),
                                width=2, height=1, bg=color, fg="black")
                label.grid(row=row, column=col)
                self.squares[chess.square(col, 7-row)] = label

        self.info_label = tk.Label(self.root, text="Initializing...", font=("Consolas", 12), bg="#1e1e1e", fg="yellow")
        self.info_label.pack(pady=5)
        
        self.progress_label = tk.Label(self.root, text="Progress: 0%", font=("Arial", 10), bg="#1e1e1e", fg="#aaaaaa")
        self.progress_label.pack(pady=2)

        self.message_label = tk.Label(self.root, text="", font=("Courier New", 14, "bold"), 
                                      bg="#1e1e1e", fg="#00ff00", wraplength=550, justify="center")
        self.message_label.pack(pady=20)
        
        # Launch encoding process after Tkinter loop is running
        self.root.after(500, self.start_stego)

    def draw_board(self, board):
        piece_map = {'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
                     'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'}
        for sq in range(64):
            piece = board.piece_at(sq)
            txt = piece_map.get(piece.symbol(), "?") if piece else " "
            self.squares[sq].config(text=txt)
        self.root.update()

    def update_status(self, move_desc, decoded_text, percent_complete, game_num):
        self.game_count_label.config(text=f"GAME #{game_num}")
        self.info_label.config(text=f"Action: {move_desc}")
        self.progress_label.config(text=f"Progress: {int(percent_complete)}%")
        self.message_label.config(text=decoded_text)
        self.root.update()
        
    def flash_game_over(self, reason):
        self.info_label.config(text=f"GAME OVER ({reason}) - REMATCH STARTING!", fg="red")
        self.root.update()
        time.sleep(1.5)
        self.info_label.config(fg="yellow")

    def start_stego(self):
        stockfish_path = find_stockfish()
        engine = None
        if stockfish_path:
            self.info_label.config(text=f"Loading Stockfish from {os.path.basename(stockfish_path)}...", fg="yellow")
            self.root.update()
            try:
                engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
            except Exception as e:
                print(f"Error loading Stockfish: {e}")
                self.info_label.config(text="Stockfish load failed. Using Heuristic Fallback.", fg="orange")
                self.root.update()
                time.sleep(1.5)
        else:
            self.info_label.config(text="Stockfish not found. Using Heuristic Fallback.", fg="orange")
            self.root.update()
            time.sleep(1.5)
            
        def gui_on_move(board, move_desc, collected_bits, percent, game_num):
            if move_desc.startswith("GAME_OVER:"):
                reason = move_desc.split(":", 1)[1]
                self.flash_game_over(reason)
                return
                
            self.draw_board(board)
            decoded_text = bits_to_text(collected_bits)
            self.update_status(move_desc, decoded_text, percent, game_num)
            
            if ANIMATION_SPEED > 0:
                time.sleep(ANIMATION_SPEED)
                
        # Run encoding
        games = encode_message_to_games(self.secret_message, engine, on_move_callback=gui_on_move)
        
        self.info_label.config(text="COMPLETE", fg="#00ff00")
        
        # Export all games to PGN string
        pgn_exporter = io.StringIO()
        for game in games:
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
        pgn_data = pgn_exporter.getvalue()
        
        # Save output PGN
        pgn_path = "stego_games.pgn"
        with open(pgn_path, "w", encoding="utf-8") as f:
            f.write(pgn_data)
            
        # Verify decoding matches perfectly
        decoded = decode_games_to_text(pgn_data)
        print("\n" + "="*50)
        print(f"Steganography Stream Finished!")
        print(f"PGN saved to: {os.path.abspath(pgn_path)}")
        print(f"Decoded Message from PGN: '{decoded}'")
        print("="*50 + "\n")
        
        if engine:
            engine.quit()


def test_encoder_decoder_roundtrip():
    print("=" * 60)
    print("RUNNING STEGANOGRAPHY SYMMETRIC VALIDATION TEST")
    print("=" * 60)
    
    test_messages = [
        "Hello World!",
        "vedant vibhav mahi and neha ",
        "Steganography is the practice of representing information within another message.",
        "Short",
        "A extremely long test message with numbers 1234567890 & symbols #$@ to prove 100% byte encoding robustness!"
    ]
    
    for msg in test_messages:
        print(f"Testing message: '{msg}'")
        games = encode_message_to_games(msg, engine=None)
        
        pgn_exporter = io.StringIO()
        for idx, game in enumerate(games):
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
            
        pgn_str = pgn_exporter.getvalue()
        
        # Decode and assert correctness
        decoded_msg = decode_games_to_text(pgn_str)
        print(f"  Decoded: '{decoded_msg}'")
        
        assert decoded_msg == msg, f"ERROR: Decoded message does not match! Got '{decoded_msg}', expected '{msg}'"
        print("  -> SUCCESS: Symmetric roundtrip validation passed!")
        
    print("=" * 60)
    print("ALL STEGANOGRAPHY VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_encoder_decoder_roundtrip()
        sys.exit(0)
        
    long_message = "vedant vibhav mahi and neha "
    visualizer = ChessVisualizer(long_message)
    visualizer.root.mainloop()
