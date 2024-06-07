#!/usr/bin/python3

import requests
import uuid
import json
import urllib.parse
import sys
import random
import time
import threading

SERVER_ADDRESS = "k8s-default-comfyuii-74cd8f9a9e-1168616089.us-east-1.elb.amazonaws.com"
HTTPS = False
SHOW_IMAGES = False
REQUEST_API_JSON = "./sdxl_refiner_prompt_api.json"

# Send prompt request to server and get prompt_id and AWSALB cookie
def queue_prompt(prompt, client_id, server_address):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    if HTTPS:
        response = requests.post("https://{}/prompt".format(server_address), data=data)
    else:
        response = requests.post("http://{}/prompt".format(server_address), data=data)
    aws_alb_cookie = response.headers['Set-Cookie'].split(';')[0]
    prompt_id = response.json()['prompt_id']
    return prompt_id, aws_alb_cookie

def get_image(filename, subfolder, folder_type, server_address, aws_alb_cookie):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    if HTTPS:
        response = requests.get("https://{}/view?{}".format(server_address, url_values), headers={"Cookie": aws_alb_cookie})
    else:
        response = requests.get("http://{}/view?{}".format(server_address, url_values), headers={"Cookie": aws_alb_cookie})
    return response.content

def get_history(prompt_id, server_address, aws_alb_cookie):
    if HTTPS:
        response = requests.get("https://{}/history/{}".format(server_address, prompt_id), headers={"Cookie": aws_alb_cookie})
    else:
        response = requests.get("http://{}/history/{}".format(server_address, prompt_id), headers={"Cookie": aws_alb_cookie})
    return response.json()

def get_images(prompt, client_id, server_address):
    prompt_id, aws_alb_cookie = queue_prompt(prompt, client_id, server_address)
    output_images = {}

    print("Generation started.")
    while True:
        history = get_history(prompt_id, server_address, aws_alb_cookie)
        if len(history) == 0:
            print("Generation not ready, sleep 1s ...")
            time.sleep(1)
            continue
        else:
            print("Generation finished.")
            break

    #history = get_history(prompt_id, server_address, aws_alb_cookie)[prompt_id]
    history = history[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'], server_address, aws_alb_cookie)
                    images_output.append(image_data)
            output_images[node_id] = images_output
    return output_images, prompt_id


def edit_prompt(prompt, sd_version):
    if sd_version == "1.5":
        # Set random seed for sd1.5
        prompt["3"]["inputs"]["seed"] = random.randint(0, sys.maxsize)
    elif sd_version == 'xl':
        # Set random seed for sdxl
        prompt["10"]["inputs"]["noise_seed"] = random.randint(0, sys.maxsize)
        prompt["11"]["inputs"]["noise_seed"] = random.randint(0, sys.maxsize)
    return prompt

def single_inference(server_address, request_api_json):
    start = time.time()
    client_id = str(uuid.uuid4())
    with open(request_api_json, "r") as f:
        prompt = json.load(f)
    if "sd1.5" in request_api_json:
        sd_version = "1.5"
    elif "sdxl" in request_api_json:
        sd_version = "xl"
    prompt = edit_prompt(prompt, sd_version)
    images, prompt_id = get_images(prompt, client_id, server_address)
    if SHOW_IMAGES:
        for node_id in images:
            for image_data in images[node_id]:
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(image_data))
                image.show()
    end = time.time()
    timespent = round((end - start), 2)
    print("Inference finished.")
    print(f"ClientID: {client_id}.")
    print(f"PromptID: {prompt_id}.")
    print(f"CKPT: {prompt['4']['inputs']['ckpt_name']}.")
    print(f"Num of images: {len(images)}.")
    print(f"Time spent: {timespent}s.")
    print("------")

if __name__ == "__main__":
    single_inference(SERVER_ADDRESS, REQUEST_API_JSON)
