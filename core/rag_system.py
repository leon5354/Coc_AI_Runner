import chromadb
from chromadb.utils import embedding_functions
import os
import hashlib

class RAGSystem:
    def __init__(self, campaign_name="default", persist_directory="./data/chroma_db"):
        self.persist_directory = persist_directory
        self.original_name = campaign_name
        self.campaign_name = self._sanitize_collection_name(campaign_name)
        
        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize Client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Embedding Function
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # Create or Get Collection (Using Sanitized Name)
        print(f"[RAG] Initializing Collection: {self.campaign_name} (from '{self.original_name}')")
        self.collection = self.client.get_or_create_collection(
            name=self.campaign_name,
            embedding_function=self.embedding_fn
        )
        
    def _sanitize_collection_name(self, name):
        """
        Converts campaign name to a valid ChromaDB collection name.
        Requirements: 3-63 chars, alphanumeric/underscore/hyphen, starts/ends with alphanumeric.
        Solution: Use 'miskatonic_' + MD5 hash of the original name.
        """
        # Create MD5 hash of the original name
        hash_object = hashlib.md5(name.encode())
        hex_dig = hash_object.hexdigest()
        
        # Format: miskatonic_HASH (e.g. miskatonic_a1b2c3d4e5f6...)
        # Max length is 63, 'miskatonic_' takes 11, MD5 is 32 -> Total 43. Safe.
        return f"miskatonic_{hex_dig}"

    def add_memory(self, text, metadata=None):
        """Adds a text snippet to the vector database."""
        if not text:
            return
            
        count = self.collection.count()
        doc_id = f"mem_{count + 1}"
        
        if metadata is None:
            metadata = {}
            
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        print(f"[RAG] Added memory {doc_id}: {text[:50]}...")

    def query_memory(self, query_text, n_results=3):
        """Retrieves relevant memories based on semantic similarity."""
        if self.collection.count() == 0:
            return []
            
        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self.collection.count())
        )
        
        if results and 'documents' in results:
            return results['documents'][0]
        return []

    def get_stats(self):
        return f"Total Memories: {self.collection.count()}"
