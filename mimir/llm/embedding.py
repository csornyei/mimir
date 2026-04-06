from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name, trust_remote_code=True)
        return self._model

    def embed(self, text: str) -> list[float]:
        return self._get_model().encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._get_model().encode(texts, normalize_embeddings=True).tolist()


embedding_model = EmbeddingModel()

if __name__ == "__main__":
    test_text = "Hello, world!"
    embedding = embedding_model.embed(test_text)
    print(f"Embedding for '{test_text}': {embedding}")
