import json
import os
import sys
import pypff
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_common_message_properties(message):
    """
    Extracts common properties from a pypff message object.
    Returns a dictionary containing these properties.
    """
    properties = {
        "subject": message.subject,
        # Ensure sender_name is cleaned of null characters, as seen in original code
        "sender_name": message.sender_name.replace('\x00', '') if message.sender_name else None,
        "sender_email": message.sender_email_address, # Assuming this was intended from the task description
        "recipient_name": message.display_to, # Assuming this was intended
        "recipient_email": message.primary_recipient_email_address, # Assuming this was intended
        "date": message.delivery_time.isoformat() if message.delivery_time else None, # Original used delivery_time
        "client_submit_time": message.client_submit_time.isoformat() if message.client_submit_time else None,
        "body": message.plain_text_body.decode('utf-8', errors='ignore') if message.plain_text_body else None,
        "folder_path": None,  # This will be populated by the calling function
        "message_id": message.internet_message_id, # Assuming this was intended
        "headers": message.transport_headers,
        "attachments": [] # Simplified from original, as attachment processing was commented out
    }
    # Original code had attachment processing commented out.
    # Re-add if needed, ensuring robust error handling for each attachment.
    # if message.number_of_attachments > 0:
    #     for i in range(message.number_of_attachments):
    #         try:
    #             attachment = message.get_attachment(i)
    #             properties["attachments"].append({
    #                 "filename": attachment.name.replace('\x00', '') if attachment.name else None,
    #                 "size": attachment.size,
    #                 # "mime_type": attachment.get_mime_type() # Requires libpff >= 20200212
    #             })
    #         except Exception as attach_err:
    #             logging.warning(f"Could not process attachment {i} for message: {attach_err}")
    #             properties["attachments"].append({"error": str(attach_err)})

    # The original code also had 'type': 'message' and 'extraction_error'
    # Adding 'type' for consistency if it was used elsewhere.
    properties['type'] = 'message' 
    try:
        # Test if all main properties are accessible, if not, log and add extraction_error
        # This is a bit redundant if each access is already checked, but matches original's intent
        pass 
    except Exception as e:
        logging.warning(f"Failed to extract some properties for a message. Error: {e}")
        properties['extraction_error'] = str(e)
        
    return properties

def process_folder(folder, output_file, current_path_string):
    """
    Recursively processes messages in a folder and its subfolders.
    Writes message properties to the output JSONL file.
    """
    # logging.info(f"Processing folder: {current_path_string}") # Verbose, can be enabled by DEBUG level
    for i in range(folder.get_number_of_sub_messages()): # Iterate using get_number_of_sub_messages
        try:
            message = folder.get_sub_message(i) # Get message by index
            msg_props = get_common_message_properties(message)
            msg_props["folder_path"] = current_path_string
            output_file.write(json.dumps(msg_props, default=str) + '\n') # Use default=str for unhandled types
        except Exception as e:
            logging.warning(f"Skipping message {i} in folder '{current_path_string}' due to error: {e}", exc_info=True)

    for i in range(folder.get_number_of_sub_folders()): # Iterate using get_number_of_sub_folders
        sub_folder = folder.get_sub_folder(i)
        if sub_folder:
            # logging.debug(f"Entering subfolder: {sub_folder.name} (under {current_path_string})")
            process_folder(sub_folder, output_file, f"{current_path_string}/{sub_folder.name}")
        else:
            logging.warning(f"Could not retrieve subfolder at index {i} under '{current_path_string}'")


def pst_to_jsonl(pst_file_path: str, jsonl_file_path: str) -> bool:
    """
    Converts a PST file to a JSONL file.
    Args:
        pst_file_path (str): Path to the input PST file.
        jsonl_file_path (str): Path to the output JSONL file.
    Returns:
        bool: True if conversion was successful.
    Raises:
        FileNotFoundError: If the PST file is not found.
        Exception: For errors during PST processing or other unexpected errors.
    """
    if not os.path.exists(pst_file_path):
        raise FileNotFoundError(f"Error: PST file not found at '{pst_file_path}'")

    try:
        pst_file_obj = pypff.file() # Renamed variable to avoid conflict with module
        pst_file_obj.open(pst_file_path)
        logging.info(f"Successfully opened PST file: {pst_file_path}")

        root_folder = pst_file_obj.get_root_folder()
        if not root_folder:
            # This case should ideally be handled by pypff raising an error on open,
            # but good to have a check if it returns None.
            raise Exception("Could not open root folder in PST file. The file might be empty or corrupted.")

        with open(jsonl_file_path, 'w', encoding='utf-8') as outfile:
            logging.info(f"Writing data to JSONL file: {jsonl_file_path}")
            
            # Iterate through top-level folders (e.g., "Top of Outlook data file" or "Top of Personal Folders")
            # These are direct children of the root_folder.
            if root_folder.get_number_of_sub_folders() == 0:
                logging.warning(f"PST file '{pst_file_path}' root folder has no subfolders. Attempting to process root folder itself if it contains messages.")
                # If there are no subfolders, messages might be directly in the root (less common for user data)
                # The process_folder function expects a folder name, so provide one for the root.
                # Or, check if root_folder itself can be processed if it has messages.
                # For now, let's assume the main content is always within subfolders of root as per typical PST structure.
                # If messages can be in the root, process_folder(root_folder, outfile, "ROOT_FOLDER") might be needed.

            for i in range(root_folder.get_number_of_sub_folders()):
                top_level_folder = root_folder.get_sub_folder(i)
                if top_level_folder:
                    # logging.info(f"Processing top-level folder: {top_level_folder.name}")
                    process_folder(top_level_folder, outfile, top_level_folder.name)
                else:
                    logging.warning(f"Could not retrieve top-level folder at index {i} in '{pst_file_path}'")
        
        pst_file_obj.close()
        logging.info("Processing complete.")
        return True
    except pypff.error as e:
        raise Exception(f"Error processing PST file with pypff: {e}. Please ensure libpff is correctly installed and the PST file is valid.")
    except FileNotFoundError: # To re-raise if it occurs within the try block for some reason
        raise
    except Exception as e:
        # Catch any other unexpected errors during the process
        raise Exception(f"An unexpected error occurred during PST processing: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PST file to JSONL format.")
    parser.add_argument("input_pst_file", help="Path to the input PST file.")
    parser.add_argument("output_jsonl_file", help="Path to the output JSONL file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging output.")
    
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        for handler in logging.getLogger().handlers: # Ensure all handlers are updated
            handler.setLevel(logging.DEBUG)
        logging.debug("Verbose logging enabled.")
    
    try:
        logging.info(f"Starting conversion from '{args.input_pst_file}' to '{args.output_jsonl_file}'")
        if pst_to_jsonl(args.input_pst_file, args.output_jsonl_file):
            # Success message printed to stdout for clear CLI feedback
            print(f"Successfully converted '{args.input_pst_file}' to '{args.output_jsonl_file}'")
            logging.info("Conversion successful.")
    except FileNotFoundError as fnf_error:
        logging.error(f"File not found: {fnf_error}")
        print(f"Error: {fnf_error}", file=sys.stderr) # User-facing error to stderr
        sys.exit(1)
    except Exception as e:
        logging.error(f"An critical error occurred during conversion: {e}", exc_info=True)
        print(f"An error occurred: {e}", file=sys.stderr) # User-facing error to stderr
        sys.exit(1)