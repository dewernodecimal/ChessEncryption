# ♟️ Chess Steganography - Infinite Stream

A highly secure and tactically natural steganography protocol that translates text messages into playable, Stockfish-optimized chess games, and back again.

---

## 🚀 Key Features

* **Symmetric Encoder/Decoder**: Translate hidden messages into PGN game files and perfectly reconstruct them with 100% precision.
* **Ambiguity-Free Protocol**: Eliminates forced-move vulnerabilities. Every move by a data piece maps unambiguously to a bit, while non-encodable states are bypassed using King moves (`SKIP`) or clean board resets.
* **Engine-Guided Natural Selection**: Uses the **Stockfish Chess Engine** to evaluate position variations and pick the most natural, high-quality chess move to transmit the secret bits, masking the hidden data from pattern analysis.
* **Robust Fallback Engine**: If Stockfish is not installed on the system, the script gracefully falls back to an intelligent heuristic move evaluation (prioritizing checks, captures, and promotions), preserving full functionality.
* **Vibrant GUI**: Built-in 8x8 Tkinter interactive board visualizer displaying Unicode chess pieces, progress meters, and real-time decoded message streams.

---

## 📜 Steganography Ruleset

| Piece Group | Bit Value / Action | Pieces |
| :--- | :--- | :--- |
| **Data 0** | `0` | Pawns (`♙`), Knights (`♘`) |
| **Data 1** | `1` | Bishops (`♗`), Rooks (`♖`), Queens (`♕`) |
| **Skip** | `SKIP` (No Data) | King (`♔`) |

* **Opening**: Every game plays a predefined standard opening sequence (first 6 plies) to speed up setup and bypass static evaluation states before encoding begins.

---

## 🛠️ Requirements & Installation

1. **Python 3.8+**
2. **chess package**:
   ```bash
   pip install python-chess
   ```

---

## 💻 Quick Start & Usage

### 1. Run the Interactive GUI
Simply run the script to launch the visualizer. It will automatically attempt to find Stockfish, fall back to heuristic mode if needed, and start transmitting a message:
```bash
python ChessEncryption.py
```

### 2. Run Automated Verification Tests
Verify the mathematical symmetry and correctness of the encoder and decoder under various text configurations:
```bash
python ChessEncryption.py --test
```

---

## 🔍 How to Programmatically Decode a PGN

Simply import the decoder function inside your scripts to extract data from any saved steganography game logs:

```python
from ChessEncryption import decode_games_to_text

# Load the saved PGN file
with open("stego_games.pgn", "r") as f:
    pgn_data = f.read()

# Decode the message
original_message = decode_games_to_text(pgn_data)
print("Decoded Secret Message:", original_message)
```

---

## 🛠️ Technical Refactoring Details

* **Robust Byte-Shift Encoding**: Replaced custom string conversions with absolute byte-shift operations to support numbers, symbols, spaces, and multi-byte UTF-8 strings.
* **Game Resets**: If the board reaches a state where neither a target bit move nor a King skip is possible, the game terminates safely, and the bitstream resumes immediately on a fresh board in `GAME #N+1`.
* **Stockfish Autolocator**: Searches your system's PATH, downloads folders, and standard workspace configurations to find `stockfish.exe` automatically.

