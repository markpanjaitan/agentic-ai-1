class AnalysisAgent:
    def __init__(self, db_agent, med_agent):
        self.db = db_agent
        self.med = med_agent
    
    def find_healthiest_top_math(self, top_n=10):
        """Find healthiest among top math performers"""
        # Get top math students
        math_students = self.db.execute_query(
            f"Find top {top_n} math performers with their emails"
        )
        
        # Get health scores
        health_scores = self.med.get_health_scores()
        
        if not math_students or not health_scores:
            return None
            
        # Combine results
        results = []
        for student in math_students:
            email = student.get('email', '').lower()
            if email in health_scores:
                results.append({
                    'name': f"{student.get('first_name', '')} {student.get('last_name', '')}",
                    'email': email,
                    'math_score': student.get('score', 0),
                    'health_score': health_scores[email],
                    'combined_score': (student.get('score', 0) * 0.7) + (health_scores[email] * 0.3)
                })
        
        if not results:
            return None
            
        return sorted(results, key=lambda x: x['combined_score'], reverse=True)[0]