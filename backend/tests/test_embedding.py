from unittest.mock import MagicMock, patch


def test_embed_texts_routes_to_voyage_when_configured():
    """Verify embed_texts calls Voyage AI when provider is set."""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1024, [0.2] * 1024]

    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result

    with patch("app.services.embedding.settings") as mock_settings, \
         patch("app.services.embedding._get_voyage_client", return_value=mock_client):
        mock_settings.embedding_provider = "voyageai"
        mock_settings.voyage_model = "voyage-3-large"

        from app.services.embedding import embed_texts
        result = embed_texts(["hello", "world"])

    assert len(result) == 2
    assert len(result[0]) == 1024
    mock_client.embed.assert_called_once_with(
        texts=["hello", "world"], model="voyage-3-large"
    )


def test_embed_texts_batches_large_inputs():
    """Verify Voyage AI path batches inputs of >128 texts."""
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1] * 1024]

    mock_client = MagicMock()
    mock_client.embed.return_value = mock_result

    with patch("app.services.embedding.settings") as mock_settings, \
         patch("app.services.embedding._get_voyage_client", return_value=mock_client):
        mock_settings.embedding_provider = "voyageai"
        mock_settings.voyage_model = "voyage-3-large"

        from app.services.embedding import embed_texts
        # 200 texts should result in 2 API calls (128 + 72)
        texts = [f"text {i}" for i in range(200)]
        mock_result.embeddings = [[0.1] * 1024] * 128
        embed_texts(texts)

    assert mock_client.embed.call_count == 2
