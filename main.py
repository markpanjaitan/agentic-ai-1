from medical_student_analysis import DatabaseAgent, MedicalAgent, AnalysisAgent
import traceback

def find_top_student():
    try:
        # Initialize all agents
        db_agent = DatabaseAgent()
        med_agent = MedicalAgent()
        analyzer = AnalysisAgent(db_agent, med_agent)
        
        # Get the healthiest top math student
        result = analyzer.find_healthiest_top_math(top_n=5)
        
        if result:
            print("\n🏆 BEST STUDENT FOUND")
            print("====================")
            print(f"Name: {result['name']}")
            print(f"Email: {result['email']}")
            print(f"Math Score: {result['math_score']}/100")
            print(f"Health Score: {result['health_score']}/100")
            print(f"Combined Score: {result['combined_score']:.1f}")
        else:
            print("❌ No matching student found")
        
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        traceback.print_exc()
    finally:
        # Clean up
        if 'db_agent' in locals():
            db_agent.close()

if __name__ == "__main__":
    find_top_student()