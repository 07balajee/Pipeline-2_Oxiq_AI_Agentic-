from datetime import datetime
from typing import List, Dict

class Timeline:
    """
    Tracks and formats key lifecycle events for a candidate's workflow run.
    Separates structural auditing from system log files.
    """
    def __init__(self):
        self._entries: List[Dict[str, str]] = []

    def add_milestone(self, description: str):
        """
        Adds a timestamped milestone entry to the workflow history.
        """
        time_str = datetime.now().strftime("%H:%M:%S")
        self._entries.append({
            "timestamp": time_str,
            "description": description
        })

    def get_entries(self) -> List[Dict[str, str]]:
        """
        Returns all registered entries.
        """
        return self._entries

    def print_timeline(self):
        """
        Prints a visual timeline box in the terminal.
        """
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(" ⏳ WORKFLOW TIMELINE TRACKER")
        for entry in self._entries:
            print(f"  {entry['timestamp']} - {entry['description']}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
