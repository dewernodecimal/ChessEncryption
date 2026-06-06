import unittest
import io
import queue
from ChessEncryption import (
    sha256_ctr_crypt,
    encrypt_payload,
    decrypt_payload,
    bytes_to_bits,
    bits_to_bytes,
    encode_message_to_games_threaded,
    decode_games_to_text,
    ThreadedStegoBot
)

class TestChessEncryption(unittest.TestCase):
    def test_bit_conversions(self):
        """Test conversion between bytes and bit arrays."""
        test_bytes = b"Hello World!"
        bits = bytes_to_bits(test_bytes)
        # 12 bytes * 8 bits = 96 bits
        self.assertEqual(len(bits), 96)
        
        reconstructed = bits_to_bytes(bits)
        self.assertEqual(reconstructed, test_bytes)

    def test_sha256_ctr_crypt_symmetry(self):
        """Test that sha256_ctr_crypt is symmetric."""
        plaintext = b"Steganography secret message"
        password = "my_secure_passcode"
        
        ciphertext = sha256_ctr_crypt(plaintext, password)
        # Ciphertext should not equal plaintext
        self.assertNotEqual(ciphertext, plaintext)
        
        decrypted = sha256_ctr_crypt(ciphertext, password)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_decrypt_payload(self):
        """Test payload encryption and decryption with magic prefix checks."""
        message = "Chess cryptographic validation test."
        password = "strongpassword"
        
        # Test with password
        ciphertext = encrypt_payload(message, password)
        success, decrypted = decrypt_payload(ciphertext, password)
        self.assertTrue(success)
        self.assertEqual(decrypted, message)
        
        # Test decryption failure with wrong password
        fail_success, fail_decrypted = decrypt_payload(ciphertext, "wrongpassword")
        self.assertFalse(fail_success)
        
        # Test without password (plain stego mode)
        ciphertext_plain = encrypt_payload(message, "")
        success_plain, decrypted_plain = decrypt_payload(ciphertext_plain, "")
        self.assertTrue(success_plain)
        self.assertEqual(decrypted_plain, message)

    def test_stego_roundtrip_no_engine(self):
        """Test end-to-end steganography encoding and decoding without Stockfish engine."""
        class DummyControl:
            is_stopped = False
            is_paused = False
            animation_speed = 0.0
            
        dummy_control = DummyControl()
        test_queue = queue.Queue()
        
        def dummy_callback(board, move_desc, collected_bits, percent, game_num, tactics=""):
            pass

        test_message = "Test message for steganography roundtrip."
        passcode = "stego123"
        
        bot = ThreadedStegoBot(engine=None, gui_queue=test_queue)
        games = encode_message_to_games_threaded(
            test_message,
            passcode,
            bot,
            dummy_callback,
            test_queue,
            dummy_control
        )
        
        self.assertTrue(len(games) > 0)
        
        # Export games to PGN string
        pgn_exporter = io.StringIO()
        for game in games:
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
            
        pgn_str = pgn_exporter.getvalue()
        
        # Decode games back to text
        decoded_msg = decode_games_to_text(pgn_str, passcode)
        self.assertEqual(decoded_msg, test_message)

    def test_unicode_messages(self):
        """Test encoding and decoding of Unicode and Emoji messages."""
        class DummyControl:
            is_stopped = False
            is_paused = False
            animation_speed = 0.0
            
        dummy_control = DummyControl()
        test_queue = queue.Queue()
        
        def dummy_callback(*args, **kwargs):
            pass

        unicode_message = "♟️ Chess Cryptography ⚡ is cool! 🦾 🔥"
        passcode = "unicode_key"
        
        bot = ThreadedStegoBot(engine=None, gui_queue=test_queue)
        games = encode_message_to_games_threaded(
            unicode_message,
            passcode,
            bot,
            dummy_callback,
            test_queue,
            dummy_control
        )
        
        pgn_exporter = io.StringIO()
        for game in games:
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
        pgn_str = pgn_exporter.getvalue()
        
        decoded_msg = decode_games_to_text(pgn_str, passcode)
        self.assertEqual(decoded_msg, unicode_message)

    def test_empty_message(self):
        """Test encoding and decoding of an empty message."""
        class DummyControl:
            is_stopped = False
            is_paused = False
            animation_speed = 0.0
            
        dummy_control = DummyControl()
        test_queue = queue.Queue()
        
        def dummy_callback(*args, **kwargs):
            pass

        empty_message = ""
        passcode = "empty"
        
        bot = ThreadedStegoBot(engine=None, gui_queue=test_queue)
        games = encode_message_to_games_threaded(
            empty_message,
            passcode,
            bot,
            dummy_callback,
            test_queue,
            dummy_control
        )
        
        pgn_exporter = io.StringIO()
        for game in games:
            pgn_exporter.write(str(game))
            pgn_exporter.write("\n\n")
        pgn_str = pgn_exporter.getvalue()
        
        decoded_msg = decode_games_to_text(pgn_str, passcode)
        self.assertEqual(decoded_msg, empty_message)

if __name__ == "__main__":
    unittest.main()
