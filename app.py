from flask import Flask, render_template, request, url_for
from xml.etree.ElementTree import ParseError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import os # For creating a safe filename and directory

app = Flask(__name__)

# --- Your YouTube Transcript Script (get_youtube_transcript function) ---
# (I've slightly modified URL parsing for common YouTube URLs)
def get_youtube_transcript(video_id_or_url):
    """
    Fetches the transcript for a given YouTube video ID or URL.

    Args:
        video_id_or_url (str): The ID or full URL of the YouTube video.

    Returns:
        str: The formatted transcript text if successful,
             or an error message if the transcript cannot be fetched.
    """
    video_id = None
    try:
        # Extract video ID if a URL is provided
        if "youtube.com/watch?v=" in video_id_or_url:  # Standard watch URL
            video_id = video_id_or_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_id_or_url:  # Shortened URL like youtu.be/VIDEO_ID
            video_id = video_id_or_url.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in video_id_or_url: # YouTube Shorts URL
             video_id = video_id_or_url.split("shorts/")[1].split("?")[0]
        else:
            # Basic check to see if it might be a valid ID (alphanumeric, -, _)
            if all(c.isalnum() or c in ['-', '_'] for c in video_id_or_url) and len(video_id_or_url) == 11:
                 video_id = video_id_or_url  # Assume it's already an ID
            else:
                # If it's not a recognized URL format or a plausible ID, it might be invalid
                return f"Invalid video ID or URL format: {video_id_or_url}"


        if not video_id: # Should have been caught by the ID check, but as a safeguard
            return f"Could not extract Video ID from: {video_id_or_url}"

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        transcript_to_fetch = None
        # Try to find English transcript first (manual, then generated)
        try:
            transcript_to_fetch = transcript_list.find_manually_created_transcript(['en'])
        except NoTranscriptFound:
            try:
                transcript_to_fetch = transcript_list.find_generated_transcript(['en'])
            except NoTranscriptFound:
                # If no English transcript, try to fetch the first available transcript
                try:
                    available_transcripts = list(transcript_list)
                    if not available_transcripts:
                        raise NoTranscriptFound("No transcripts available at all for this video.")
                    transcript_to_fetch = available_transcripts[0]
                    print(
                        f"Info: No English transcript found. Using transcript in '{transcript_to_fetch.language_code}' (Language: {transcript_to_fetch.language}).")
                except NoTranscriptFound: # Reraise if still not found
                    raise
                except Exception as ex_fallback:
                    return f"No English transcript found and failed to fetch an alternative for video: {video_id_or_url}. Error: {ex_fallback}"

        if not transcript_to_fetch: # Should be handled by earlier logic, but good to have
            return f"Could not determine a transcript to fetch for video: {video_id_or_url}"

        transcript_data = transcript_to_fetch.fetch()

        formatted_transcript = ""
        for i, entry in enumerate(transcript_data):
            try:
                formatted_transcript += entry['text'] + " "
            except TypeError as te:
                if "is not subscriptable" in str(te).lower():
                    if hasattr(entry, 'text'):
                        try:
                            formatted_transcript += entry.text + " "
                        except Exception as e_attr:
                            print(
                                f"Error: Segment {i} for video {video_id} was not subscriptable and accessing '.text' attribute failed: {e_attr}. Segment type: {type(entry)}.")
                            formatted_transcript += "[text extraction failed] "
                    else:
                        print(
                            f"Error: Segment {i} for video {video_id} was not subscriptable and no '.text' attribute found. Segment type: {type(entry)}.")
                        formatted_transcript += "[text extraction failed] "
                else:
                    raise # Reraise other TypeErrors
            except KeyError:
                print(f"Warning: Segment {i} for video {video_id} is missing 'text' key. Segment: {entry}")
                formatted_transcript += "[text key missing] "
            except Exception as e_loop:
                print(f"Error: Unexpected issue with segment {i} for video {video_id}: {e_loop}. Segment: {entry}")
                formatted_transcript += "[segment processing error] "

        return formatted_transcript.strip()

    except TranscriptsDisabled:
        return f"Transcripts are disabled for the video: {video_id_or_url}"
    except NoTranscriptFound:
        err_msg = f"No transcript could be found for the video: {video_id_or_url}."
        if video_id:
            err_msg += f" (Processed Video ID: {video_id})."
        err_msg += " This could be due to an incorrect video ID, the video not having any transcripts, the video being unavailable, or the requested language not being available."
        return err_msg
    except ParseError as pe:
        err_msg = f"XML ParseError: {pe}. This often occurs with live streams (like '{video_id}'), videos with no valid transcript data, or if YouTube returns an empty/malformed transcript file."
        if video_id:
            err_msg += f" (While processing Video ID: {video_id})"
        return err_msg
    except Exception as e:
        err_msg = f"An unexpected error occurred: {type(e).__name__} - {str(e)}"
        if video_id:
            err_msg += f" (While processing Video ID: {video_id})"
        return err_msg
# --- End of your script ---

@app.route('/', methods=['GET', 'POST'])
def index():
    transcript_text = None
    error_message = None
    filename_on_server = None # To inform the user where the file is saved on the server (if saved)

    if request.method == 'POST':
        video_input = request.form.get('video_url')
        if not video_input:
            error_message = "Please enter a YouTube Video ID or URL."
        else:
            transcript_text = get_youtube_transcript(video_input)

            # Check if the result is an error message (as your function returns strings for errors)
            is_error = False
            error_indicators = [
                "Transcripts are disabled", "No transcript", "An unexpected error occurred",
                "Could not determine", "XML ParseError", "Invalid video ID",
                "[text extraction failed]", "[text key missing]", "[segment processing error]"
            ]
            for indicator in error_indicators:
                if transcript_text.startswith(indicator) or indicator in transcript_text:
                    is_error = True
                    break

            if is_error:
                error_message = transcript_text
                transcript_text = None # Clear transcript if it's an error
            elif not transcript_text: # Handles case where empty string might be returned for non-errors
                 error_message = "No transcript content was generated or fetched."
            else:
                # --- Save the transcript to a file on the server (optional but as in your original script) ---
                # It's good practice to save files in a dedicated directory.
                # Ensure this directory exists and your application has write permissions.
                save_directory = "saved_transcripts"
                if not os.path.exists(save_directory):
                    try:
                        os.makedirs(save_directory)
                    except OSError as e:
                        print(f"Error creating directory {save_directory}: {e}")
                        # Optionally, inform the user or handle the error
                        error_message = (error_message or "") + f" (Could not create save directory on server: {e})"


                # Attempt to extract a video ID for the filename, similar to your original script
                vid_id_part = video_input
                if "v=" in video_input:
                    vid_id_part = video_input.split("v=")[1].split("&")[0]
                elif "youtu.be/" in video_input:
                    vid_id_part = video_input.split("/")[-1].split("?")[0]
                elif "youtube.com/shorts/" in video_input:
                    vid_id_part = video_input.split("shorts/")[1].split("?")[0]
                # else, vid_id_part remains the original input if it's already an ID

                safe_vid_id = "".join(c for c in vid_id_part if c.isalnum() or c in ('_', '-')).strip()[:50]
                if not safe_vid_id: safe_vid_id = "unknown_video"

                filename_on_server_temp = f"transcript_{safe_vid_id}.txt"
                filepath = os.path.join(save_directory, filename_on_server_temp)

                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    filename_on_server = filename_on_server_temp # Confirm filename if save is successful
                    print(f"Transcript saved to {filepath}")
                except Exception as e:
                    print(f"Error saving transcript to file {filepath}: {e}")
                    # Append to existing error message or create new if none
                    error_detail = f" (Transcript fetched, but error saving to file: {e})"
                    error_message = (error_message + error_detail) if error_message else error_detail[1:] # remove leading space if no prior error
                    filename_on_server = None # Don't show filename if saving failed

    return render_template('index.html', transcript=transcript_text, error=error_message, filename=filename_on_server)

if __name__ == '__main__':
    # For development, you can run it like this:
    # app.run(debug=True, port=5000)
    # For production on Digital Ocean, Gunicorn will typically run the app.
    # Make sure the host is '0.0.0.0' to be accessible externally from the container.
    app.run(host='0.0.0.0', port=5000)
