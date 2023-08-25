import modal

def download_whisper():
  # Load the Whisper model
  import os
  import whisper
  print ("Download the Whisper model")

  # Perform download only once and save to Container storage
  whisper._download(whisper._MODELS["medium"], '/content/podcast/', False)


stub = modal.Stub("corise-podcast-project")
corise_image = modal.Image.debian_slim().pip_install("feedparser",
                                                     "https://github.com/openai/whisper/archive/9f70a352f9f8630ab3aa0d06af5cb9532bd8c21d.tar.gz",
                                                     "requests",
                                                     "ffmpeg",
                                                     "openai",
                                                     "tiktoken",
                                                     "wikipedia",
                                                     "ffmpeg-python").apt_install("ffmpeg").run_function(download_whisper)

@stub.function(image=corise_image, gpu="any", timeout=600)
def get_transcribe_podcast(rss_url, local_path):
  print ("Starting Podcast Transcription Function")
  print ("Feed URL: ", rss_url)
  print ("Local Path:", local_path)

  # Read from the RSS Feed URL
  import feedparser
  intelligence_feed = feedparser.parse(rss_url)
  podcast_title = intelligence_feed['feed']['title']
  episode_title = intelligence_feed.entries[0]['title']
  episode_image = intelligence_feed['feed']['image'].href
  for item in intelligence_feed.entries[0].links:
    if (item['type'] == 'audio/mpeg'):
      episode_url = item.href
  episode_name = "podcast_episode.mp3"
  print ("RSS URL read and episode URL: ", episode_url)

  # Download the podcast episode by parsing the RSS feed
  from pathlib import Path
  p = Path(local_path)
  p.mkdir(exist_ok=True)

  print ("Downloading the podcast episode")
  import requests
  with requests.get(episode_url, stream=True) as r:
    r.raise_for_status()
    episode_path = p.joinpath(episode_name)
    with open(episode_path, 'wb') as f:
      for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

  print ("Podcast Episode downloaded")

  # Load the Whisper model
  import os
  import whisper

  # Load model from saved location
  print ("Load the Whisper model")
  model = whisper.load_model('medium', device='cuda', download_root='/content/podcast/')

  # Perform the transcription
  print ("Starting podcast transcription")
  result = model.transcribe(local_path + episode_name)

  # Return the transcribed text
  print ("Podcast transcription completed, returning results...")
  output = {}
  output['podcast_title'] = podcast_title
  output['episode_title'] = episode_title
  output['episode_image'] = episode_image
  output['episode_transcript'] = result['text']
  return output

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"))
def get_podcast_summary(podcast_transcript):
  import openai
  openai.api_key = secret #'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'
  instructPrompt = """
  I want you to step into the role of an experienced copywriter responsible for publishing newsletters to thousands of subscribers. Your task is to summarize a podcast episode in a concise and simple manner, highlighting the important topics discussed. Please follow these guidelines:

  1. Start by providing a brief introduction to the podcast episode, including its title and host.
  2. Summarize the main points or key takeaways from the episode, focusing on the most important topics discussed.
  3. Use clear and concise language to ensure your summary is easily understandable by a wide range of readers.
  4. Aim to keep the summary to a specific length limit (e.g., 150-200 words) to make it more reader-friendly and appealing.
  5. Avoid adding any personal opinions or additional information beyond what was discussed in the podcast episode.
  6. Proofread your summary before publishing to ensure accuracy and clarity.
  7. Consider formatting options such as bullet points or subheadings to organize your summary effectively.

  Remember, your goal is to engage and inform the subscribers, so make sure your summary is interesting, accurate, and compelling.
  The transcript of the podcast is provided below."
  """

  request = instructPrompt + podcast_transcript
  chatOutput = openai.ChatCompletion.create(model="gpt-3.5-turbo-16k",
                                            messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                      {"role": "user", "content": request}
                                                      ]
                                            )
  podcastSummary = chatOutput.choices[0].message.content

  return podcastSummary

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"))
def get_podcast_demographic(podcast_transcript):
  import openai
  openai.api_key = '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'
  instructPrompt = """
  You are an experienced economic news reporter. Suggest three demographic of readers that will be interested in this episode after analyzing the content of the podcast. 
  Cap the description of the demographic under five words.

  - Demographic 1
  - Demographic 2
  - Demographic 3
  """

  request = instructPrompt + podcast_transcript
  chatOutput = openai.ChatCompletion.create(model="gpt-3.5-turbo-16k",
                                              messages=[{"role": "system", "content": "You are a helpful assistant."},
                                                        {"role": "user", "content": request}
                                                        ]
                                              )
  podcastDemographic = chatOutput.choices[0].message.content
  return podcastDemographic

@stub.function(image=corise_image, secret=modal.Secret.from_name("my-openai-secret"), timeout=1200)
def process_podcast(url, path):
  output = {}
  podcast_details = get_transcribe_podcast.call(url, path)
  podcast_summary = get_podcast_summary.call(podcast_details['episode_transcript'])
  podcast_demographic = get_podcast_demographic.call(podcast_details['episode_transcript'])
  output['podcast_details'] = podcast_details
  output['podcast_summary'] = podcast_summary
  output['podcast_demographic'] = podcast_demographic
  return output

@stub.local_entrypoint()
def test_method(url, path):
  output = {}
  podcast_details = get_transcribe_podcast.call(url, path)
  print ("Podcast Summary: ", get_podcast_summary.call(podcast_details['episode_transcript']))
  # print ("Podcast Guest Information: ", get_podcast_guest.call(podcast_details['episode_transcript']))
  print ("Podcast Demographic: ", get_podcast_demographic.call(podcast_details['episode_transcript']))
