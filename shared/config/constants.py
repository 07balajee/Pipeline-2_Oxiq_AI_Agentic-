# OxiqAI Pipeline-2 State Machine Constants

# 1. State Names
STATE_CANDIDATE_SHORTLISTED = "CandidateShortlisted"
STATE_INTERVIEW_SCHEDULING = "InterviewScheduling"
STATE_INTERVIEW_SCHEDULED = "InterviewScheduled"
STATE_TECHNICAL_INTERVIEW_PENDING = "TechnicalInterviewPending"
STATE_TECHNICAL_INTERVIEW_COMPLETED = "TechnicalInterviewCompleted"
STATE_HR_INTERVIEW_PENDING = "HRInterviewPending"
STATE_HR_INTERVIEW_COMPLETED = "HRInterviewCompleted"
STATE_CANDIDATE_SELECTED = "CandidateSelected"
STATE_CANDIDATE_REJECTED = "CandidateRejected"
STATE_CANDIDATE_WAITLISTED = "CandidateWaitlisted"
STATE_OFFER_PIPELINE_TRIGGERED = "OfferPipelineTriggered"
STATE_WORKFLOW_COMPLETED = "WorkflowCompleted"
STATE_WORKFLOW_FAILED = "WorkflowFailed"
STATE_WORKFLOW_PAUSED = "WorkflowPaused"
STATE_WORKFLOW_RESUMED = "WorkflowResumed"

# 2. Event Names
EVENT_CANDIDATE_SHORTLISTED = "CandidateShortlisted"
EVENT_INTERVIEW_CREATED = "InterviewCreated"
EVENT_INTERVIEW_RESCHEDULED = "InterviewRescheduled"
EVENT_INTERVIEW_CANCELLED = "InterviewCancelled"
EVENT_INTERVIEW_STARTED = "InterviewStarted"
EVENT_TECHNICAL_SCORE_SUBMITTED = "TechnicalScoreSubmitted"
EVENT_TRIGGER_HR_ROUND = "TriggerHRRound"
EVENT_HR_SCORE_SUBMITTED = "HRScoreSubmitted"
EVENT_CANDIDATE_RANKED = "CandidateRanked"
EVENT_CANDIDATE_SELECTED = "CandidateSelected"
EVENT_CANDIDATE_REJECTED = "CandidateRejected"
EVENT_CANDIDATE_WAITLISTED = "CandidateWaitlisted"
EVENT_OFFER_REQUESTED = "OfferRequested"
EVENT_WORKFLOW_PAUSED = "WorkflowPaused"
EVENT_WORKFLOW_RESUMED = "WorkflowResumed"
EVENT_WORKFLOW_FAILED = "WorkflowFailed"
EVENT_RETRY_REQUESTED = "RetryRequested"

# 3. Agent Registry Keys
AGENT_INVITATION = "agent6"
AGENT_TECHNICAL = "agent7"
AGENT_HR_RANKING = "agent8"

# 4. Tool / MCP Registry Keys
TOOL_DATABASE = "database_mcp"
TOOL_CALENDAR = "calendar_mcp"
TOOL_MEET = "meet_mcp"
TOOL_SMTP = "smtp_mcp"
TOOL_RESUME = "resume_mcp"
TOOL_NOTIFICATION = "notification_mcp"

# 5. Execution Parameters
MAX_RETRY_ATTEMPTS = 3
DEFAULT_EXPONENTIAL_BACKOFF_BASE = 2
DEFAULT_TIMEOUT_SECONDS = 30
PIPELINE_TRACE_VERSION = "1.0.0"
