import json
import os

notebook = {
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "# 🚀 Host Ollama on a Free Cloud GPU (Google Colab)\n",
        "This notebook installs Ollama, pulls your models, and exposes them securely to the public internet using a Cloudflare tunnel.\n",
        "**Instructions:**\n",
        "1. Go to the top menu and click **Runtime > Change runtime type**.\n",
        "2. Select **T4 GPU** and click Save.\n",
        "3. Click **Runtime > Run all**.\n",
        "4. Scroll to the very bottom to get your public API URL!"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "!curl -fsSL https://ollama.com/install.sh | sh"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "import os\n",
        "import threading\n",
        "import time\n",
        "\n",
        "def run_ollama():\n",
        "    os.system('OLLAMA_HOST=0.0.0.0 ollama serve')\n",
        "\n",
        "# Start Ollama in the background\n",
        "threading.Thread(target=run_ollama, daemon=True).start()\n",
        "time.sleep(3) # Wait for server to start"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "!ollama pull llama3.2\n",
        "!ollama pull nomic-embed-text"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "# Download and install cloudflared for the public tunnel\n",
        "!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb\n",
        "!dpkg -i cloudflared-linux-amd64.deb"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "import subprocess\n",
        "import threading\n",
        "import time\n",
        "import re\n",
        "\n",
        "def run_cloudflared():\n",
        "    # Run cloudflared tunnel\n",
        "    process = subprocess.Popen(\n",
        "        ['cloudflared', 'tunnel', '--url', 'http://127.0.0.1:11434'],\n",
        "        stdout=subprocess.PIPE,\n",
        "        stderr=subprocess.STDOUT,\n",
        "        text=True\n",
        "    )\n",
        "    for line in process.stdout:\n",
        "        if \"trycloudflare.com\" in line:\n",
        "            url = re.search(r'https://[-a-zA-Z0-9]+\\.trycloudflare\\.com', line)\n",
        "            if url:\n",
        "                print(\"\\n\" + \"=\"*70)\n",
        "                print(f\"🚀 YOUR PUBLIC OLLAMA API URL IS: {url.group(0)}\")\n",
        "                print(\"=\"*70 + \"\\n\")\n",
        "                print(\"Replace 'http://localhost:11434' in your VectorDB project with this URL!\")\n",
        "                break\n",
        "\n",
        "# Start tunnel in the background\n",
        "threading.Thread(target=run_cloudflared, daemon=True).start()\n",
        "\n",
        "# Keep the notebook running so the tunnel doesn't close\n",
        "while True:\n",
        "    time.sleep(60)"
      ]
    }
  ],
  "metadata": {
    "colab": {
      "provenance": []
    },
    "kernelspec": {
      "display_name": "Python 3",
      "name": "python3"
    },
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 0
}

with open('e:/Project/VectorDB/Ollama_Cloud_GPU.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=2)

print("Notebook created")
