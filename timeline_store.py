"""
Timeline Store - In-memory storage for live session findings
"""

from datetime import datetime
from typing import List, Dict

class TimelineStore:
    """Store timeline entries for live session"""
    
    def __init__(self):
        self.timeline: List[str] = []
    
    def add(self, finding: str):
        """Add a finding to the timeline"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {finding}"
        self.timeline.append(entry)
        print(f"📝 Added to timeline: {finding[:100]}")
    
    def all(self) -> List[str]:
        """Get all timeline entries"""
        return self.timeline
    
    def clear(self):
        """Clear all timeline entries"""
        self.timeline = []
        print("🗑️ Timeline cleared")
    
    def get_recent(self, n: int = 10) -> List[str]:
        """Get n most recent entries"""
        return self.timeline[-n:] if self.timeline else []
    
    def count(self) -> int:
        """Get count of entries"""
        return len(self.timeline)