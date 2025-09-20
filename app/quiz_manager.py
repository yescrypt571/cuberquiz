import time

class QuizManager:
    def __init__(self):
        # {group_id: {"quiz_id": 123456, "owner": user_id, "size": 10, "questions": []}}
        self.active_quizzes = {}

    def start_quiz(self, user_id, group_id, size):
        quiz_id = int(time.time())  # Vaqt asosida unique id
        self.active_quizzes[group_id] = {
            "quiz_id": quiz_id,
            "owner": user_id,
            "size": size,
            "questions": [],
        }
        return quiz_id

    def add_question(self, group_id, question, options, correct_index):
        if group_id not in self.active_quizzes:
            return False
        self.active_quizzes[group_id]["questions"].append({
            "question": question,
            "options": options[:],  # Variantlar nusxasi, tartib o'zgarmasligi uchun
            "correct_index": correct_index,
            "poll_id": None
        })
        return True

    def set_poll_id(self, group_id, q_index, poll_id):
        if group_id in self.active_quizzes:
            if 0 <= q_index < len(self.active_quizzes[group_id]["questions"]):
                self.active_quizzes[group_id]["questions"][q_index]["poll_id"] = poll_id

    def is_quiz_ready(self, group_id):
        data = self.active_quizzes.get(group_id)
        return data and len(data["questions"]) >= data["size"]

    def get_quiz(self, group_id):
        return self.active_quizzes.get(group_id)

    def get_quiz_id(self, group_id):
        quiz = self.active_quizzes.get(group_id)
        return quiz["quiz_id"] if quiz else None

    def clear_quiz(self, group_id):
        if group_id in self.active_quizzes:
            del self.active_quizzes[group_id]

    def get_group_quiz(self, group_id):
        quiz = self.active_quizzes.get(group_id)
        return quiz["quiz_id"] if quiz else None