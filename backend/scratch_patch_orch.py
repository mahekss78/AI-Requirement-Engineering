with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix 1: Stage 0 Normalization - Segment sentences correctly
import re
target1 = """                    # Check for speaker format "Name: statement"
                    speaker_match = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)*):\\s*(.+)", line)
                    if speaker_match:
                        speaker = speaker_match.group(1)
                        content = speaker_match.group(2)
                        metadata.append({"type": "SPEAKER_ATTRIBUTION", "content": f"Speaker: {speaker}"})
                        statements.append({"statement_id": f"STMT-{stmt_idx:03d}", "content": content})
                    else:
                        statements.append({"statement_id": f"STMT-{stmt_idx:03d}", "content": line})
                    stmt_idx += 1"""
replacement1 = """                    # Check for speaker format "Name: statement"
                    speaker_match = re.match(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)*):\\s*(.+)", line)
                    if speaker_match:
                        speaker = speaker_match.group(1)
                        content = speaker_match.group(2)
                        metadata.append({"type": "SPEAKER_ATTRIBUTION", "content": f"Speaker: {speaker}"})
                    else:
                        content = line
                        
                    # Split sentences properly
                    sentences = re.split(r'(?<=[.!?])\\s+(?=[A-Z])', content)
                    for sent in sentences:
                        sent = sent.strip()
                        if sent:
                            statements.append({"statement_id": f"STMT-{stmt_idx:03d}", "content": sent})
                            stmt_idx += 1"""
text = text.replace(target1, replacement1)

# Fix 2: User Story Structuring - Remove Acceptance Criteria, differentiate as_a / draft_as_a
target2 = """                if not norm_actor:
                    norm_actor = "an authorized system user"
                    actor_evidence_status = "NOT_EXPLICITLY_SUPPORTED"

                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": norm_actor,
                    "i_want": f"to {action}",
                    "so_that": None,
                    "source_evidence": {
                        "actor": norm_actor if actor_evidence_status == "EXPLICITLY_SUPPORTED" else None,
                        "action": action,
                        "external_system": external_system,
                        "business_outcome": None
                    },
                    "actor_evidence_status": actor_evidence_status,
                    "acceptance_criteria": [
                        {
                            "scenario": "Default Success",
                            "given": "valid prerequisites",
                            "when": "action is triggered",
                            "then": "success"
                        }
                    ],
                    "relationship_references": [],
                    "secondary_aspects_preserved": [
                        {"type": "EXTERNAL_INTEGRATION", "subtype": "DATA_EXCHANGE"}
                    ] if external_system else [],
                    "clarification_status": clarification_status,
                    "human_approval_status": "DRAFT"
                })"""

replacement2 = """                if not norm_actor:
                    norm_actor = None
                    actor_evidence_status = "NOT_EXPLICITLY_SUPPORTED"
                    draft_as_a = "an authorized system user"
                else:
                    draft_as_a = None

                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": norm_actor,
                    "draft_as_a": draft_as_a,
                    "i_want": f"to {action}",
                    "so_that": None,
                    "source_evidence": {
                        "actor": norm_actor if norm_actor else None,
                        "action": action,
                        "external_system": external_system,
                        "business_outcome": None
                    },
                    "actor_evidence_status": actor_evidence_status,
                    "relationship_references": [],
                    "secondary_aspects_preserved": [
                        {"type": "EXTERNAL_INTEGRATION", "subtype": "DATA_EXCHANGE"}
                    ] if external_system else [],
                    "clarification_status": clarification_status,
                    "human_approval_status": "DRAFT"
                })"""
text = text.replace(target2, replacement2)


# Fix 3: Integration Specification Hallucinations
target3 = """                integration_specifications.append({
                    "int_id": f"INT-{len(integration_specifications)+1:03d}",
                    "statement_id": stmt_id,
                    "source_system": "Core Application",
                    "target_system": target_system,
                    "interaction_purpose": "Data Sync",
                    "data_exchanged": None,
                    "trigger": None,
                    "direction": "BIDIRECTIONAL",
                    "protocol": "REST API",
                    "unspecified_details_requiring_clarification": [
                        "Data schema",
                        "Authentication"
                    ],
                    "source_evidence": {
                        "statement": content
                    },
                    "relationship_references": [],
                    "clarification_status": "INTEGRATION_DETAILS_REQUIRE_REVIEW",
                    "human_approval_status": "DRAFT"
                })"""
replacement3 = """                integration_specifications.append({
                    "int_id": f"INT-{len(integration_specifications)+1:03d}",
                    "statement_id": stmt_id,
                    "source_system": None,
                    "target_system": target_system,
                    "interaction_purpose": None,
                    "data_exchanged": None,
                    "trigger": None,
                    "direction": None,
                    "protocol": None,
                    "unspecified_details_requiring_clarification": [
                        "Source application identity",
                        "Interaction purpose",
                        "Data exchanged",
                        "Interaction direction",
                        "Trigger",
                        "Protocol/interface",
                        "Authentication"
                    ],
                    "source_evidence": {
                        "statement": content
                    },
                    "relationship_references": [],
                    "clarification_status": "INTEGRATION_DETAILS_REQUIRE_REVIEW",
                    "human_approval_status": "DRAFT"
                })"""
text = text.replace(target3, replacement3)


with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'w', encoding='utf-8') as f:
    f.write(text)
