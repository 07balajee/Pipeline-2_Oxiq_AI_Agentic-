from typing import List, Optional, Tuple, Dict, Any
from agents.agent6.models import Interviewer, InterviewMode
from shared.context.workflow_context import WorkflowContext
from shared.logger.logger import workflow_logger

class InterviewerSelector:
    """
    Selects interviewers from mocked data profiles using deterministic scoring.
    """
    def __init__(self):
        # Mock database list of interviewers
        self.mock_interviewers: List[Interviewer] = [
            Interviewer(
                interviewer_id="int-1",
                name="Priya Singh",
                role="Senior AI Engineer",
                department="Engineering",
                skills=["Python", "Transformers", "Pydantic", "Machine Learning"],
                supported_interview_types=["Technical"],
                supported_modes=["Online", "Offline"],
                is_active=True
            ),
            Interviewer(
                interviewer_id="int-2",
                name="Aman Verma",
                role="Staff Research Scientist",
                department="Research",
                skills=["Python", "Research", "Deep Learning", "Mathematics"],
                supported_interview_types=["Technical"],
                supported_modes=["Online"],
                is_active=True
            ),
            Interviewer(
                interviewer_id="int-3",
                name="Rahul Sharma",
                role="Director of HR",
                department="People Operations",
                skills=["Communication", "Leadership", "Culture Fit"],
                supported_interview_types=["HR"],
                supported_modes=["Online", "Offline"],
                is_active=True
            ),
            Interviewer(
                interviewer_id="int-4",
                name="Sarah Connor",
                role="Lead DevOps Engineer",
                department="Engineering",
                skills=["Docker", "Kubernetes", "AWS", "Python"],
                supported_interview_types=["Technical"],
                supported_modes=["Offline"],
                is_active=True
            ),
            Interviewer(
                interviewer_id="int-5",
                name="John Connor",
                role="Software Engineer",
                department="Engineering",
                skills=["React", "TypeScript", "Node.js"],
                supported_interview_types=["Technical"],
                supported_modes=["Online", "Offline"],
                is_active=False  # Inactive to verify active status filter
            )
        ]

    def select_interviewer(
        self, 
        context: WorkflowContext, 
        job_payload: Dict[str, Any], 
        mode: InterviewMode
    ) -> Optional[Tuple[Interviewer, Dict[str, Any]]]:
        """
        Suggests the highest-ranked active interviewer qualified for the job and mode.
        """
        eligible_interviewers = []
        rejected_recommendations = context.metadata.get("rejected_recommendations", [])
        
        # Candidate job department mapping (derived from title if missing)
        job_dept = job_payload.get("department")
        if not job_dept:
            job_title_lower = job_payload.get("job_title", "").lower()
            if "engineer" in job_title_lower or "developer" in job_title_lower or "ai" in job_title_lower:
                job_dept = "Engineering"
            elif "research" in job_title_lower or "scientist" in job_title_lower:
                job_dept = "Research"
            else:
                job_dept = "People Operations"

        for interviewer in self.mock_interviewers:
            # 1. Filter: Active Status
            if not interviewer.is_active:
                continue
                
            # 2. Filter: Interview Type Match
            if "Technical" not in interviewer.supported_interview_types:
                continue
                
            # 3. Filter: Mode Compatibility
            if mode.value not in interviewer.supported_modes:
                continue
                
            # 4. Fetch Availability Slots (via Calendar MCP)
            from agents.agent6.tools import Agent6ToolsAdapter
            try:
                availability_resp = Agent6ToolsAdapter.fetch_calendar_availability(
                    interviewer.interviewer_id, context.workflow_id, context.metadata
                )
                if availability_resp.status != "SUCCESS":
                    raise Exception(f"Calendar MCP query failed: {availability_resp.errors}")
                slots = availability_resp.payload
                if not isinstance(slots, list):
                    raise ValueError("Malformed Calendar response: payload must be a list of slots")
            except Exception as e:
                if "Calendar MCP query failed" in str(e) or "Malformed Calendar" in str(e):
                    raise e
                workflow_logger.logger.error(f"Error fetching calendar availability: {e}")
                continue

            # 5. Filter: Check if there is at least one non-rejected slot
            non_rejected_slots = []
            for slot_label in slots:
                is_rejected = False
                for rejected in rejected_recommendations:
                    if (rejected.get("interviewer_id") == interviewer.interviewer_id 
                            and rejected.get("time_slot") == slot_label):
                        is_rejected = True
                        break
                if not is_rejected:
                    non_rejected_slots.append(slot_label)

            if not non_rejected_slots:
                # Discard interviewer if all slots are rejected/conflicting
                continue

            # 6. Deterministic Scoring
            # Dept Match: 40 points
            dept_match = (job_dept == interviewer.department)
            dept_score = 40 if dept_match else 0
            
            # Skill Match: 10 points per matching skill, max 40 points
            job_skills = job_payload.get("technical_criteria", [])
            overlapping_skills = list(set(job_skills).intersection(interviewer.skills))
            skill_score = min(40, len(overlapping_skills) * 10)
            
            # Mode Capability: 20 points if supports both modes, 10 if only one
            mode_score = 20 if len(interviewer.supported_modes) >= 2 else 10
            
            total_score = dept_score + skill_score + mode_score
            
            # Reasons for explainability
            reasons = []
            if dept_match:
                reasons.append(f"✓ {interviewer.department} Department Match")
            else:
                reasons.append(f"✗ Department Mismatch (Expected: {job_dept}, Got: {interviewer.department})")
                
            reasons.append(
                f"✓ {len(overlapping_skills)} Skill Match{'es' if len(overlapping_skills) != 1 else ''} "
                f"({', '.join(overlapping_skills) if overlapping_skills else 'None'})"
            )
            reasons.append("✓ Technical Interview Qualified")
            reasons.append(f"✓ Available for {mode.value} Mode")

            score_breakdown = {
                "total_score": total_score,
                "department_score": dept_score,
                "skill_score": skill_score,
                "mode_score": mode_score,
                "reasons": reasons
            }

            eligible_interviewers.append((interviewer, score_breakdown))

        if not eligible_interviewers:
            workflow_logger.logger.warning("No eligible interviewers found after filtering.", extra={"trace_id": context.workflow_id})
            return None

        # Rank eligible interviewers: highest total_score first
        eligible_interviewers.sort(key=lambda x: x[1]["total_score"], reverse=True)
        
        # Display the found count in interactive runs
        is_interactive = context.metadata.get("interactive", False)
        if is_interactive:
            print(f"\nFinding eligible interviewers...")
            print(f"\n{len(eligible_interviewers)} eligible interviewer{'s' if len(eligible_interviewers) != 1 else ''} found.")

        # Return the top recommendation
        return eligible_interviewers[0]

