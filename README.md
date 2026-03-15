<p align="center">
  <img src="media/KITE_LOGO-removebg.png" alt="K.I.T.E. Logo" width="450" />
</p>
<h3 align="center">Kernel Integrated Task Engine</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Ollama-Local_AI-FF4B4B?style=for-the-badge" alt="Ollama" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector_Store-00A650?style=for-the-badge" alt="ChromaDB" />

</p>

<p align="center">
  <strong>A fully local, modular AI agent and voice assistant powered by Model Context Protocol skills.</strong>
</p>

<br />

## Overview

K.I.T.E. is an advanced conversational system designed to run entirely offline on your local machine. It combines the reasoning capabilities of local language models with a robust skill routing engine, allowing it to seamlessly answer questions or delegate complex tasks to structured scripts and API destinations.

By prioritizing privacy, performance, and flexibility, K.I.T.E. ensures your data never leaves your environment while granting you a powerful voice enabled assistant.


## Architecture Highlights

1. **Registry and Retrieval**: New capabilities are defined in a simple JSON registry. On startup, K.I.T.E. embeds these definitions into a highly optimized vector store.
2. **Conversation Loop**: The entrypoint continuously accepts user input, routes decisions, and synthesizes speech in an event driven loop.
3. **Execution Engine**: When a tool is invoked, the executor safely processes the request and returns a raw result, which is then summarized naturally for audio output.

## Installation

Begin by cloning the repository and running the provided installation script. The script will automatically set up your virtual environment, install Python dependencies, pull the required Ollama model, and start the application.

```bash
git clone https://github.com/BerpyDerpy/K.I.T.E.git
cd KITE_v3
chmod +x install
./install
```

Ensure you have Ollama installed globally before running the script.

## Usage

Start the main conversational loop to bring K.I.T.E. online.

```bash
python main.py
```

The system will initialize its ChromaDB index, load the available capabilities, and greet you via its TTS engine. Simply type your query at the command prompt to interact.

## Configuration

All local capabilities and endpoints are registered in `registry/skills.json`. You can easily extend K.I.T.E. by adding new entries to this file and implementing the corresponding logic in the `skills` directory. Environment variables for advanced configuration can be placed in a `.env` file at the project root.
