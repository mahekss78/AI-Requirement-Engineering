import asyncio
import uuid
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, Requirement
from app.services.runner import CapabilityRunner

async def main():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    runner = CapabilityRunner()

    texts = {
        'University': '''Students can register for courses if they satisfy the prerequisites.
Can students register for a course after the deadline?
What happens if the student information system is unavailable?
One advisor said late registration should be allowed until midnight, while the registrar said registration closes at 5 PM.
Registration should be completed within 3 seconds.
The platform must support 8,000 concurrent students.
Data must be retained for 7 years.
Academic Advisor can approve registration exceptions.
The system should check prerequisite completion before registration.
Students can search available courses.
System must integrate with University Student Information System.''',

        'E-Commerce': '''Customer can cancel unfulfilled orders within 30 minutes of placement.
Support agents can override cancellation limits for VIP customers.
Refund processing notifications must be delivered within 2 seconds.
The application should be much faster during flash sales.
The system should integrate with the Stripe Payment Gateway.
Can partially shipped orders be cancelled?
Refunds should normally complete within 5 business days.
Another stakeholder said refunds must happen immediately.''',

        'Library Management': '''Library members can borrow up to 5 books at a time.
Can members borrow reference books?
The system should integrate with the National Library Database.
Librarian can waive late fees for first-time offenders.
Search results must load within 1 second.
The application must handle 200 concurrent users.
One branch manager said the borrowing period is 14 days, while another said it should be 21 days.
What is the procedure for lost books?
Members can place a hold on unavailable books.
System sends SMS notification when a held book becomes available.'''
    }

    for domain, text in texts.items():
        print(f'\n=== TESTING {domain.upper()} ===')
        try:
            req_id = uuid.uuid4()
            req = Requirement(id=req_id, project_id=uuid.uuid4(), title=domain, current_state="DRAFT")
            db.add(req)
            db.commit()

            result_req = runner.run_pipeline(db, req_id, document_content=text, domain_context=domain)
            
            data = result_req.requirement_data or {}
            
            print(f'  State: {result_req.current_state}')
            
            extraction = data.get("extraction", {})
            structuring = data.get("structuring", {})
            conflicts_data = data.get("conflict_detection", {})

            actors = extraction.get("actors", [])
            print(f'  Actors: {actors}')
            
            integrations = extraction.get("external_integrations", [])
            print(f'  Integrations: {integrations}')
            
            questions = [q.get("question") or q.get("statement") for q in extraction.get("open_questions", [])]
            print(f'  Questions: {questions}')
            
            nfrs = extraction.get("non_functional_requirements", [])
            print(f'  NFRs count: {len(nfrs)}')
            for nfr in nfrs:
                print(f'    - {nfr.get("statement", "")}')
                
            conflicts = conflicts_data.get("conflicts", [])
            print(f'  Conflicts count: {len(conflicts)}')
            for conf in conflicts:
                print(f'    - {conf.get("conflict_description", "")}')
                
            user_stories = structuring.get("user_stories", [])
            print(f'  User Stories count: {len(user_stories)}')
            for us in user_stories:
                print(f'    [{us.get("id")}] As a {us.get("as_a")}, I want to {us.get("i_want")}')
                for ac in us.get("acceptance_criteria", []):
                    print(f'      * {ac.get("scenario")}')
                    for given in ac.get("given", []): print(f'        GIVEN {given}')
                    for when in ac.get("when", []): print(f'        WHEN {when}')
                    for then in ac.get("then", []): print(f'        THEN {then}')
        except Exception as e:
            print(f'Error processing {domain}: {e}')

if __name__ == '__main__':
    asyncio.run(main())
