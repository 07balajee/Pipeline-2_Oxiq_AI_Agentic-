from agents.agent6.models import InterviewMode
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class ModeSelector:
    """
    Handles Online vs Offline interview mode selection.
    Coordinates interactive prompt selections and programmatic fallback logic.
    """

    def select_mode(self, context: WorkflowContext) -> InterviewMode:
        """
        Selects the interview mode.
        """
        is_interactive = context.metadata.get("interactive", False)
        
        if not is_interactive:
            # 1. Check metadata first
            meta_mode = context.metadata.get("interview_mode")
            if meta_mode:
                if meta_mode.lower() == "online":
                    return InterviewMode.ONLINE
                elif meta_mode.lower() == "offline":
                    return InterviewMode.OFFLINE
                    
            # 2. Check profile notes
            notes = getattr(context.candidate, "profile_notes", "") or ""
            notes_lower = notes.lower()
            if "online" in notes_lower:
                return InterviewMode.ONLINE
            elif "offline" in notes_lower:
                return InterviewMode.OFFLINE
                
            # Default fallback
            workflow_logger.info(
                f"Programmatic run: selected default mode '{InterviewMode.ONLINE.value}'", 
                trace_id=context.workflow_id
            )
            return InterviewMode.ONLINE

        # Interactive Mode prompting and hardening
        while True:
            print("\nInterview Mode:")
            print("  1. Online")
            print("  2. Offline")
            choice = input("\n> ").strip().lower()
            
            if choice == "1" or choice == "online":
                return InterviewMode.ONLINE
            elif choice == "2" or choice == "offline":
                return InterviewMode.OFFLINE
            else:
                print("\n[Validation Error] Invalid choice. Please enter '1' for Online or '2' for Offline.")

