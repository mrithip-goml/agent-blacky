import os
import subprocess
import re
from google import genai
from google.genai import types
from config.settings import GEMINI_API_KEY

class CLIAssistant:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Check your .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-flash"

        self.forbidden_patterns = [
            r"\bsudo\b", r"\bsu\b", r"\bchown\b",
            r"rm\s+-rf\s+/", r"rm\s+-rf\s+~",
            r">\s*/dev/sd", r"mkfs", r"dd\s+if="
        ]

    def is_safe_command(self, command: str) -> tuple[bool, str]:
        for pattern in self.forbidden_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Forbidden command pattern detected: {pattern}"
        return True, "Safe"

    def generate_command(self, user_prompt: str) -> str:
        system_instruction = (
            "You are Blacky, a Linux CLI assistant running on Ubuntu with Niri Wayland.\n"
            "Translate the user request into a single valid POSIX/bash command.\n"
            "STRICT RULES:\n"
            "1. NO sudo or elevated permissions.\n"
            "2. Operate strictly within user home or current directory permissions.\n"
            "3. Output raw bash command ONLY with NO markdown codeblocks or quotes."
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1
            )
        )
        cmd = response.text.strip().replace("```bash", "").replace("```", "").strip()
        return cmd

    def execute_command(self, command: str) -> str:
        is_safe, reason = self.is_safe_command(command)
        if not is_safe:
            return f"[ERROR] Security Triggered: {reason}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15,
                executable="/bin/bash"
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            output = ""
            if stdout:
                output += stdout
            if stderr:
                output += f"\n[STDERR]: {stderr}" if output else stderr
            return output if output else "[Command executed cleanly with no output]"

        except subprocess.TimeoutExpired:
            return "[ERROR] Command timed out after 15 seconds."
        except Exception as e:
            return f"[ERROR] Execution failed: {str(e)}"

    def process_smart_query(self, user_input: str) -> str:
        """Determines if query needs system execution, runs it, and formats a concise response."""
        system_instruction = (
            "You are Blacky, an AI companion running locally on an Ubuntu Linux system.\n"
            "The user asked a query about their local machine or system state.\n"
            "First, generate the appropriate user-level non-sudo bash command to retrieve this info."
        )
        
        # Step A: Get command
        cmd = self.generate_command(user_input)
        is_safe, reason = self.is_safe_command(cmd)
        
        if not is_safe:
            return f"I cannot execute that command due to security restrictions ({reason})."

        # Step B: Run command locally
        output = self.execute_command(cmd)

        # Step C: Summarize result concisely
        summary_prompt = (
            f"User asked: '{user_input}'\n"
            f"Command executed: `{cmd}`\n"
            f"Raw command output:\n{output}\n\n"
            "Provide a direct, concise response in 1-2 clean sentences summarizing the key information. "
            "Include the command executed for transparency."
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=summary_prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are Blacky, a concise Linux terminal assistant. Be direct, clear, and brief."
            )
        )
        return response.text