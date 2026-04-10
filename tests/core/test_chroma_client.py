"""Tests for core/db/chroma_client.py — domain-isolated vector search."""

import pytest
from unittest.mock import MagicMock, patch

from core.db.chroma_client import ChromaClient


class TestChromaClientInit:
    """Test ChromaDB client initialization."""

    def test_default_config(self):
        client = ChromaClient()
        assert client._host == "localhost"
        assert client._port == 8000
        assert client.is_connected is False

    def test_custom_config(self):
        client = ChromaClient(host="chroma.local", port=9000)
        assert client._host == "chroma.local"
        assert client._port == 9000

    def test_not_connected_initially(self):
        client = ChromaClient()
        assert client.is_connected is False


class TestCollectionNaming:
    """Test domain-isolated collection naming."""

    def test_collection_name_format(self):
        client = ChromaClient()
        name = client._collection_name("kisanmitra", "schemes")
        assert name == "kisanmitra_schemes"

    def test_collection_name_different_apps(self):
        client = ChromaClient()
        name1 = client._collection_name("kisanmitra", "prices")
        name2 = client._collection_name("vyapaar", "prices")
        assert name1 != name2
        assert name1 == "kisanmitra_prices"
        assert name2 == "vyapaar_prices"


class TestGracefulDegradation:
    """Test behavior when ChromaDB is not available."""

    def test_get_collection_when_disconnected(self):
        client = ChromaClient()
        coll = client.get_or_create_collection("app", "coll")
        assert coll is None

    def test_add_documents_when_disconnected(self):
        client = ChromaClient()
        # Should not raise — logs warning and returns
        client.add_documents("app", "coll", ["doc1", "doc2"])

    def test_search_when_disconnected(self):
        client = ChromaClient()
        results = client.search("app", "coll", "query")
        assert results == []

    def test_delete_collection_when_disconnected(self):
        client = ChromaClient()
        # Should not raise
        client.delete_collection("app", "coll")


class TestConnectedOperations:
    """Test operations with a mocked ChromaDB client."""

    def _make_connected_client(self):
        client = ChromaClient()
        client._client = MagicMock()
        client._connected = True
        return client

    def test_get_or_create_collection(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll

        result = client.get_or_create_collection("kisanmitra", "schemes")
        assert result == mock_coll
        client._client.get_or_create_collection.assert_called_once_with(
            name="kisanmitra_schemes"
        )

    def test_add_documents_with_ids(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll

        client.add_documents(
            "app", "coll",
            documents=["doc1", "doc2"],
            ids=["id1", "id2"],
        )
        mock_coll.add.assert_called_once_with(
            documents=["doc1", "doc2"],
            ids=["id1", "id2"],
        )

    def test_add_documents_auto_ids(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll

        client.add_documents("app", "coll", documents=["doc1", "doc2"])
        call_kwargs = mock_coll.add.call_args[1]
        assert len(call_kwargs["ids"]) == 2
        assert call_kwargs["ids"][0] == "app_coll_0"

    def test_add_documents_with_metadatas(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll

        metas = [{"key": "val1"}, {"key": "val2"}]
        client.add_documents(
            "app", "coll",
            documents=["doc1", "doc2"],
            metadatas=metas,
            ids=["id1", "id2"],
        )
        call_kwargs = mock_coll.add.call_args[1]
        assert call_kwargs["metadatas"] == metas

    def test_search_returns_results(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll
        mock_coll.query.return_value = {
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{"k": "v1"}, {"k": "v2"}]],
            "distances": [[0.1, 0.5]],
        }

        results = client.search("app", "coll", "query text", n_results=2)
        assert len(results) == 2
        assert results[0]["document"] == "doc1"
        assert results[0]["metadata"] == {"k": "v1"}
        assert results[0]["distance"] == 0.1

    def test_search_with_where_filter(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll
        mock_coll.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        client.search("app", "coll", "query", where={"state": "MP"})
        call_kwargs = mock_coll.query.call_args[1]
        assert call_kwargs["where"] == {"state": "MP"}

    def test_search_handles_exception(self):
        client = self._make_connected_client()
        mock_coll = MagicMock()
        client._client.get_or_create_collection.return_value = mock_coll
        mock_coll.query.side_effect = RuntimeError("connection lost")

        results = client.search("app", "coll", "query")
        assert results == []

    def test_delete_collection(self):
        client = self._make_connected_client()
        client.delete_collection("app", "coll")
        client._client.delete_collection.assert_called_once_with("app_coll")
