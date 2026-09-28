import re

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/runner.py', 'r', encoding='utf-8') as f:
    text = f.read()

imports = '''from app.capabilities.structuring import structuring_capability
from app.capabilities.nfr_specification import nfr_specification_capability
from app.capabilities.integration_specification import integration_specification_capability'''

text = text.replace('from app.capabilities.structuring import structuring_capability', imports)

exec_code = '''            # -------------------------------------------------------------- #
            # Step 4: Structuring Capabilities (US, NFR, INT)
            # -------------------------------------------------------------- #
            logger.info(f"[PIPELINE {correlation_id}][CAP 4/6] User Story Structuring START")
            structuring_res = structuring_capability.execute({
                "ready_for_us": ready_for_us,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["structuring"] = structuring_res
            logger.info(f"[PIPELINE {correlation_id}][CAP 4/6] User Story Structuring DONE | ai_status={structuring_res.get('ai_status')}")

            logger.info(f"[PIPELINE {correlation_id}][CAP 4B] NFR Structuring START")
            ready_for_nfr = [s for s in ready_statements if "NFR_SPECIFICATION" in s.get("artifact_routes", [])]
            nfr_res = nfr_specification_capability.execute({
                "ready_for_nfr": ready_for_nfr,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["nfr_structuring"] = nfr_res

            logger.info(f"[PIPELINE {correlation_id}][CAP 4C] INT Structuring START")
            ready_for_int = [s for s in ready_statements if "INTEGRATION_SPECIFICATION" in s.get("artifact_routes", [])]
            int_res = integration_specification_capability.execute({
                "ready_for_int": ready_for_int,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["int_structuring"] = int_res
'''

pattern = re.compile(r'            # -------------------------------------------------------------- #\n            # Step 4: Structuring Capability\n            # -------------------------------------------------------------- #.*?logger\.info\(f"\[PIPELINE \{correlation_id\}\]\[CAP 4/6\] User Story Structuring DONE \| ai_status=\{structuring_res\.get\(\'ai_status\'\)\}"\)\n', re.DOTALL)

new_text = pattern.sub(lambda m: exec_code, text)

# Ensure the requirement data gets updated with the NFR and INT data
replace_req = '''
            # Write final JSON payload
            req.requirement_data = {
                "source": req.document_text,
                "extracted_data": extracted_res,
                "context_enrichment": context_res,
                "gap_analysis": gap_res,
                "conflict_detection": conflict_res,
                "structured_requirement": structuring_res,
                "nfr_specifications": nfr_res,
                "integration_specifications": int_res,
                "classification": classification,
                "quality_score": quality_res,
                "stage1_registry": registry_data,
                "stage2_relationships": relationships
            }
'''

pattern2 = re.compile(r'            # Write final JSON payload\n            req\.requirement_data = \{.*?\}', re.DOTALL)
new_text = pattern2.sub(lambda m: replace_req, new_text)

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/runner.py', 'w', encoding='utf-8') as f:
    f.write(new_text)

print(len(text), len(new_text))
