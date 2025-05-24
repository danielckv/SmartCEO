import json
import os
import sys
import pypff


def get_common_message_properties(message):
    """Extracts common properties from a pypff message object."""
    properties = {}
    try:
        properties['type'] = 'message'
        properties['subject'] = message.subject
        properties['sender_name'] = message.sender_name.replace('\x00', '') if message.sender_name else None
        properties['client_submit_time'] = message.client_submit_time.isoformat() if message.client_submit_time else None
        properties['delivery_time'] = message.delivery_time.isoformat() if message.delivery_time else None

        # Prefer HTML body if available, fallback to plain text
        # Ensure body is not None before attempting strip() or handling
        body_content = message.plain_text_body if message.plain_text_body else None
        # Simple cleanup: replace potential null characters or strip whitespace
        properties['body'] = body_content if body_content else None
        properties['transport_headers'] = message.transport_headers if message.transport_headers else None


        # Extract attachment metadata
        attachments = []
        # for i in range(message.get_number_of_attachments()):
        #     attachment = message.get_attachment(i)
        #     attachments.append({
        #         'name': attachment.name.replace('\x00', '') if attachment.name else None,
        #         'file_name': attachment.file_name.replace('\x00', '') if attachment.file_name else None,
        #         'size': attachment.size,
        #         'creation_time': attachment.creation_time.isoformat() if attachment.creation_time else None,
        #         'modification_time': attachment.modification_time.isoformat() if attachment.modification_time else None,
        #         # Note: Does NOT extract attachment content to keep JSON manageable
        #     })
        # properties['attachments'] = attachments

        # You could add more properties here by inspecting the pypff.message object
        # Example: properties['importance'] = message.importance
        # Example: properties['priority'] = message.priority

    except Exception as e:
        # Log or print error for a specific message if extraction fails
        print(f"Warning: Failed to extract common properties for a message. Error: {e}", file=sys.stderr)
        # Return partial properties or an error indicator
        properties['extraction_error'] = str(e)

    return properties

# Modified process_folder to accept current_path
def process_folder(folder, output_file, current_path_string):
    """Recursively processes a folder and its subfolders, passing down the path."""
    print(f"Processing folder: {current_path_string}")

    # Process messages in the current folder
    for i in range(folder.get_number_of_sub_messages()):
        try:
            message = folder.get_sub_message(i)
            message_data = get_common_message_properties(message)

            # Add the current, correctly tracked folder path
            message_data['folder_path'] = current_path_string

            # Write message data as a JSON line
            json_line = json.dumps(message_data, ensure_ascii=False, default=str) # Use default=str for any unhandled types
            output_file.write(json_line + '\n')

        except Exception as e:
            print(f"Warning: Skipping message {i} in folder '{current_path_string}' due to error: {e}", file=sys.stderr)


    # Recursively process subfolders
    for i in range(folder.get_number_of_sub_folders()):
        sub_folder = folder.get_sub_folder(i)
        # Construct the path for the subfolder
        sub_folder_path = f"{current_path_string}/{sub_folder.name}" if current_path_string else sub_folder.name
        process_folder(sub_folder, output_file, sub_folder_path)


def pst_to_jsonl(pst_file_path, jsonl_file_path):
    """Reads a PST file and writes its contents to a JSONL file."""
    if not os.path.exists(pst_file_path):
        print(f"Error: PST file not found at '{pst_file_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        pst = pypff.file()
        pst.open(pst_file_path)
        print(f"Successfully opened PST file: {pst_file_path}")

        root_folder = pst.get_root_folder()

        # Open the output JSONL file in write mode with UTF-8 encoding
        with open(jsonl_file_path, 'w', encoding='utf-8') as outfile:
            print(f"Writing data to JSONL file: {jsonl_file_path}")

            # In pypff, the actual user data folders are usually children of the root.
            # These are the visible "Top of Personal Folders" or similar.
            # We iterate through these top-level children and start the recursive
            # process, passing their name as the initial path.
            for i in range(root_folder.get_number_of_sub_folders()):
                 top_level_folder = root_folder.get_sub_folder(i)
                 # Start the path with the name of this top-level folder
                 process_folder(top_level_folder, outfile, top_level_folder.name)

            # Note: The root_folder itself rarely contains user messages in typical PSTs,
            # but if it did, you might need logic here too. The above loop
            # processing sub_folders of the root covers the common case.


        pst.close()
        print("Processing complete.")

    except pypff.error as e:
        print(f"Error processing PST file: {e}", file=sys.stderr)
        print("Please ensure libpst is installed and the PST file is valid.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python your_script_name.py <input_pst_file> <output_jsonl_file>")
        sys.exit(1)

    input_pst = sys.argv[1]
    output_jsonl = sys.argv[2]

    pst_to_jsonl(input_pst, output_jsonl)