import os
from openai import OpenAI
from models import User, PayrollRecord, LeaveRequest

def analyze_payroll_data(db_session, user_prompt=None):
    """
    Analyzes payroll and employee data to provide insights.
    Uses OpenAI if API key is present, otherwise returns a rule-based mock.
    """
    api_key = os.environ.get("AI_API_KEY")
    
    # Fetch data for context
    total_payroll = db_session.query(PayrollRecord).all()
    total_users = User.query.count()
    pending_leaves = LeaveRequest.query.filter_by(status='Pending').count()
    
    context = f"""
    System State:
    - Total Employees: {total_users}
    - Total Payroll Records: {len(total_payroll)}
    - Pending Leave Requests: {pending_leaves}
    """

    if not api_key:
        if user_prompt:
            return f"Offline Analysis: Your query '{user_prompt}' is received. Currently, I only provide automated insights based on system triggers in offline mode. Workforce: {total_users}."
        
        if pending_leaves > 5:
            return "Management Alert: High volume of pending leave requests. HR intervention recommended."
        return "System Analysis: Payroll expenditure is within normal parameters."

    try:
        client = OpenAI(api_key=api_key)
        
        system_msg = "You are an AI Payroll Consultant. Provide a single-sentence executive insight based on the data. Be professional and concise."
        user_msg = f"{context}\n\nUser Question: {user_prompt}" if user_prompt else f"{context}\n\nProvide a general status insight."
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=80
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Service Error: {str(e)}"
