from core.vector_store import VectorStoreManager

vector_store = VectorStoreManager(
    persist_directory="vector_stores/48dbe0f4-992b-4e36-975b-9857e26a9b81/3fd43bc9-e9d3-42d2-8b80-9e2b8842791d/chroma_db"
)

db = vector_store.load_or_create()

print(db._collection.count())