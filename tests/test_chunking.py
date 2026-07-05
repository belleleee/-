from unittest import TestCase

from risk_himate.app.core.chunking import chunk_text


class ChunkingTests(TestCase):
    def test_chunk_text_preserves_chunk_ids(self) -> None:
        text = "第一段介绍智能推荐系统。第二句补充说明。\n\n第二段提到数据跨境传输和用户隐私。"
        chunks = chunk_text(text, max_chars=18)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_id, "chunk-000")
        self.assertTrue(all(chunk.text for chunk in chunks))
