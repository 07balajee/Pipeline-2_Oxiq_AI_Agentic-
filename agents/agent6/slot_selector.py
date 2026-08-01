from typing import List, Optional, Tuple, Dict, Any
from agents.agent6.models import InterviewSlot
from agents.agent6.tools import Agent6ToolsAdapter
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class SlotSelector:
    """
    Selects and ranks scheduling slots from calendar availability queried via Calendar MCP.
    """

    def select_slot(
        self, 
        context: WorkflowContext, 
        interviewer_id: str
    ) -> Optional[Tuple[InterviewSlot, str]]:
        """
        Retrieves availability, filters conflicts and working hours, and ranks the best slot.
        """
        # Fetch timeslots dynamically via Calendar MCP
        availability_resp = Agent6ToolsAdapter.fetch_calendar_availability(
            interviewer_id, context.workflow_id, context.metadata
        )
        
        # Print telemetry trace details for the query call
        self._print_mcp_telemetry(availability_resp)

        if availability_resp.status != "SUCCESS":
            raise Exception(f"Calendar MCP query failed: {availability_resp.errors}")
        if not isinstance(availability_resp.payload, list):
            raise ValueError("Malformed Calendar response: payload must be a list of slots")
            
        rejected_recommendations = context.metadata.get("rejected_recommendations", [])
        candidate_pref = context.metadata.get("candidate_preference")
        
        day_map = {
            "monday": 1, "tuesday": 2, "wednesday": 3, 
            "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7
        }

        ranked_slots = []
        for idx, slot_label in enumerate(availability_resp.payload):
            # 1. Conflict Check: Skip if this interviewer/slot pair was rejected
            is_rejected = False
            for rejected in rejected_recommendations:
                if (rejected.get("interviewer_id") == interviewer_id 
                        and rejected.get("time_slot") == slot_label):
                    is_rejected = True
                    break
            if is_rejected:
                continue

            # Parse label (e.g. "Monday 10:00 AM")
            parts = slot_label.split()
            if len(parts) != 3:
                # Malformed format, skip
                continue

            day_name = parts[0].lower()
            time_str = parts[1]
            ampm = parts[2].upper()

            try:
                hour = int(time_str.split(":")[0])
                minute = int(time_str.split(":")[1])
                
                # Convert hour to 24-hour format
                hour_24 = hour
                if ampm == "PM" and hour != 12:
                    hour_24 += 12
                elif ampm == "AM" and hour == 12:
                    hour_24 = 0

                # 2. Working Hours Filter: 9:00 AM to 5:00 PM (17:00)
                if not (9 <= hour_24 < 17):
                    continue

                day_val = day_map.get(day_name, 8)
                chronological_score = day_val * 24 * 60 + hour_24 * 60 + minute

            except Exception:
                # Parser error, skip slot
                continue

            # 3. Candidate Preference Matching
            pref_score = 0
            has_pref_match = False
            if candidate_pref:
                pref_lower = candidate_pref.lower()
                if pref_lower in slot_label.lower():
                    pref_score += 100
                    has_pref_match = True
                if "morning" in pref_lower and ampm == "AM":
                    pref_score += 50
                    has_pref_match = True
                elif "afternoon" in pref_lower and ampm == "PM":
                    pref_score += 50
                    has_pref_match = True

            slot_model = InterviewSlot(
                slot_id=f"slot-{idx+1}", 
                label=slot_label, 
                is_available=True
            )
            
            ranked_slots.append({
                "slot": slot_model,
                "pref_score": pref_score,
                "has_pref_match": has_pref_match,
                "chrono_score": chronological_score
            })

        if not ranked_slots:
            return None

        # Sort slots: higher preference score first, then earlier chronological score
        ranked_slots.sort(key=lambda x: (-x["pref_score"], x["chrono_score"]))

        # List all available ranked slots for interactive trace prints
        is_interactive = context.metadata.get("interactive", False)
        if is_interactive:
            print("\nChecking Calendar MCP...")
            print("\nAvailable Slots:")
            for rank, item in enumerate(ranked_slots):
                is_recommended = " — Recommended" if rank == 0 else ""
                print(f"  {rank + 1}. {item['slot'].label}{is_recommended}")

        # Determine explainable reason
        best_item = ranked_slots[0]
        if best_item["has_pref_match"]:
            reason = "Earliest availability matching candidate preference."
        else:
            reason = "Earliest conflict-free availability."

        return best_item["slot"], reason

    def _print_mcp_telemetry(self, response):
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"[{response.mcp_name} - fetch_availability]")
        print(f"  Status        : {response.status}")
        print(f"  Trace ID      : {response.trace_id}")
        print(f"  Workflow ID   : {response.workflow_id}")
        print(f"  Execution Time: {response.execution_time_ms:.1f} ms")
        if isinstance(response.payload, list):
            print(f"  Payload       : {response.payload}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

