import unittest
from unittest.mock import patch
import json
import sys
import os

# Adjust sys.path to include the src directory
# This allows the test runner to find vector_engine.src.app
# Assumes the tests are run from the root of the project or similar context
# where 'vector_engine' is a direct subdirectory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Now import the modules from src
try:
    from app import search_emails_gradio, iface
    # Attempt to import perform_search_logic to check if it's available for patching
    # This also helps confirm the sys.path modification is working as expected.
    from db_explorer import perform_search_logic 
except ImportError as e:
    # Provide a more informative error if imports fail
    raise ImportError(f"Failed to import app components. Check sys.path and file locations. Original error: {e}")


class TestGradioApp(unittest.TestCase):

    def test_app_imports_and_interface_creation(self):
        """Test that the Gradio interface object is created."""
        self.assertIsNotNone(iface, "Gradio interface 'iface' should not be None.")

    @patch('app.perform_search_logic') # Patching where it's looked up (in the 'app' module)
    def test_search_emails_gradio_function_success(self, mock_perform_search):
        """Test search_emails_gradio function with a successful search."""
        sample_response = {
            "ids": [["id1"]],
            "documents": [["Test Email content"]],
            "metadatas": [[{"subject": "Test Email"}]],
            "distances": [[0.1]]
        }
        mock_perform_search.return_value = sample_response

        query = "test query"
        db_path = "dummy_db_path"
        collection = "dummy_collection"
        
        result_json = search_emails_gradio(query, db_path, collection)
        
        mock_perform_search.assert_called_once_with(
            query=query,
            db_path=db_path,
            collection_name=collection,
            use_ollama_parsing=False,
            n_results=10
        )
        
        expected_json = json.dumps(sample_response, indent=2, ensure_ascii=False)
        self.assertEqual(result_json, expected_json)

    @patch('app.perform_search_logic') # Patching where it's looked up (in the 'app' module)
    def test_search_emails_gradio_function_exception(self, mock_perform_search):
        """Test search_emails_gradio function when perform_search_logic raises an exception."""
        error_message = "Test DB not found"
        mock_perform_search.side_effect = LookupError(error_message)

        query = "another query"
        db_path = "dummy_db_path"
        collection = "dummy_collection"

        result_json = search_emails_gradio(query, db_path, collection)
        
        mock_perform_search.assert_called_once_with(
            query=query,
            db_path=db_path,
            collection_name=collection,
            use_ollama_parsing=False,
            n_results=10
        )
        
        # The actual error message in app.py is "Error finding collection or data: {le}"
        expected_error_response = {"error": f"Error finding collection or data: {error_message}"}
        # The result from search_emails_gradio should be a JSON string
        self.assertEqual(json.loads(result_json), expected_error_response)

if __name__ == '__main__':
    unittest.main()
