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

    def requires_system_execution(self, user_prompt: str) -> bool:
        """Determines if a prompt requires inspecting the local system/files."""
        router_prompt = (
            "Analyze the user's prompt and determine if answering it requires inspecting or running commands "
            "on the user's local Linux machine (e.g., checking files, dotfiles, disk, processes, hardware, time, settings, system specs).\n"
            "Respond with EXACTLY 'EXEC' if it needs system inspection, or 'CHAT' if it is a general question, coding advice, or explanation.\n\n"
            f"User Prompt: {user_prompt}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=router_prompt,
            config=types.GenerateContentConfig(temperature=0.0)
        )
        return "EXEC" in response.text.strip().upper()

    def generate_command(self, user_prompt: str) -> str:
        system_instruction = (
            "You are Blacky, a Linux CLI assistant running on Ubuntu with Niri Wayland.\n"
            "Translate the user request into a single valid POSIX/bash command to inspect or get data from the system.\n"
            "If the user asks about system configuration or customizations, check ~/.config/ or shell dotfiles (~/.bashrc, etc.).\n"
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
        return response.text.strip().replace("```bash", "").replace("```", "").strip()

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

    def handle_user_query(self, user_input: str) -> str:
        """Seamlessly routes to either direct chat or shell execution + summary."""
        if self.requires_system_execution(user_input):
            cmd = self.generate_command(user_input)
            is_safe, reason = self.is_safe_command(cmd)
            
            if not is_safe:
                return f"I cannot execute that command due to security restrictions ({reason})."

            output = self.execute_command(cmd)

            summary_prompt = (
                f"User Query: '{user_input}'\n"
                f"Executed Command: `{cmd}`\n"
                f"Command Output:\n{output}\n\n"
                "Summarize the command output clearly and directly to answer the user's question. "
                "Include the executed command at the end in parentheses."
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=summary_prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are Blacky, a direct Linux terminal assistant. Synthesize raw command output into clean prose."
                )
            )
            return response.text
        else:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction="You are Blacky, a concise Linux terminal assistant running on Ubuntu Niri. Keep responses brief, direct, and well-structured."
                )
            )
            return response.text