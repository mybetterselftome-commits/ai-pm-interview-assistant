# This makes `prompts` a proper package
# Import all prompt variables so they're accessible via `from prompts import ...`
from .profile_prompt import profile_prompt
from .jd_prompt import jd_prompt
from .interview_prompt import interview_prompt
from .knowledge_prompt import knowledge_prompt
from .agent_prompt import agent_prompt

__all__ = [
    'profile_prompt',
    'jd_prompt',
    'interview_prompt',
    'knowledge_prompt',
    'agent_prompt'
]
