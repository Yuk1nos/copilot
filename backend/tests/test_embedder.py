from unittest.mock import patch, MagicMock
from src.embedder import Embedder


class TestEmbedder:
    def test_embed_returns_vector(self):
        with patch("src.embedder.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_vec = MagicMock()
            mock_vec.tolist.return_value = [0.1] * 384
            mock_model.encode.return_value = mock_vec
            mock_st.return_value = mock_model

            embedder = Embedder()
            vec = embedder.embed("测试文本")
            assert len(vec) == 384

    def test_embed_batch_returns_multiple_vectors(self):
        with patch("src.embedder.SentenceTransformer") as mock_st:
            mock_model = MagicMock()
            mock_vec = MagicMock()
            mock_vec.tolist.return_value = [[0.1] * 384, [0.2] * 384]
            mock_model.encode.return_value = mock_vec
            mock_st.return_value = mock_model

            embedder = Embedder()
            vecs = embedder.embed_batch(["文本1", "文本2"])
            assert len(vecs) == 2
            assert len(vecs[0]) == 384
