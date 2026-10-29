import tempfile
import unittest
from pathlib import Path
from core.logbook import LogBook, Entry, OK, INFO, WARN, ERROR, DEBUG


class TestLogBook(unittest.TestCase):

    def test_instantiation_without_file(self):
        log = LogBook()
        self.assertIsNone(log.file_path)
        entry = log.add(INFO, "test message")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.text, "test message")
        self.assertEqual(entry.level, INFO)
        self.assertEqual(len(log.entries()), 1)

    def test_instantiation_with_file_writes_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "logs" / "app.log"
            log = LogBook(file_path=file_path)
            self.assertEqual(log.file_path, file_path)
            log.add(INFO, "hello log file")
            self.assertTrue(file_path.exists())
            content = file_path.read_text(encoding="utf-8")
            self.assertIn("[INFO] hello log file", content)

    def test_debug_filtering(self):
        log = LogBook()
        log.debug_enabled = False
        self.assertIsNone(log.add(DEBUG, "hidden"))
        self.assertEqual(len(log.entries()), 0)
        log.debug_enabled = True
        self.assertIsNotNone(log.add(DEBUG, "visible"))
        self.assertEqual(len(log.entries()), 1)

    def test_clear_entries(self):
        log = LogBook()
        log.add(OK, "success")
        self.assertEqual(len(log.entries()), 1)
        log.clear()
        self.assertEqual(len(log.entries()), 0)


if __name__ == "__main__":
    unittest.main()
