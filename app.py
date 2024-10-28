import datetime
from flask import Flask, jsonify, render_template, redirect, url_for, request, session, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, send
from flask_sqlalchemy import SQLAlchemy
import cohere
from textblob import TextBlob

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)
cohere_client = cohere.Client("9K4WKP7kbXPQGvLclv3BZrtAbgzl7M3hR9zwfv5X")

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship('User', backref=db.backref('questions', lazy=True))

with app.app_context():
    db.create_all()

# Create tables
@app.before_first_request
def create_tables():
    db.create_all()

# Resource recommendation logic
new_query = {
    "mental health": [
        {"title": "Understanding Mental Health", "url": "https://example.com/mental-health"},
        {"title": "Coping Strategies for Mental Health", "url": "https://example.com/coping-strategies"}
    ],
    "anxiety": [
        {"title": "Coping with Anxiety", "url": "https://example.com/anxiety"},
        {"title": "Anxiety Relief Techniques", "url": "https://example.com/relief"}
    ],
    "depression": [
        {"title": "Dealing with Depression", "url": "https://example.com/depression"}
    ]
}

# Educational Modules Route
@app.route('/educational-modules', methods=['GET', 'POST'])
def educational_modules():
    module_content = ""
    topic = ""
    
    if request.method == 'POST':
        topic = request.form.get('topic')
        if topic:
            response = cohere_client.generate(
                model='command-xlarge-nightly',
                prompt=(
                    f"Write a comprehensive educational module on the topic of {topic}. "
                    "List the key points below in bullet format, each on a new line:\n"
                ),
                max_tokens=600,
                temperature=0.5,
            )
            module_content = response.generations[0].text.strip()

    return render_template('educational_modules.html', module_content=module_content, topic=topic)

@app.route('/self-assessment', methods=['GET', 'POST'])
def self_assessment():
    # Initialize session variables if not already present
    if 'questions' not in session:
        session['questions'] = []
    if 'answers' not in session:
        session['answers'] = []
    if 'options' not in session:
        session['options'] = []
    
    # Number of questions and predefined options
    total_questions = 5
    options = ["Never", "Sometimes", "Often", "Always"]

    # Generate questions if not already done
    if not session['questions']:
        # Using Cohere to generate questions based on a mental health topic
        response = cohere_client.generate(
            model='command-xlarge-nightly',
            prompt='Generate 5 self-assessment questions for mental health awareness.',
            max_tokens=150,
            temperature=0.5
        )
        questions = response.generations[0].text.strip().split('\n')
        
        # Store questions and options in the session
        session['questions'] = questions[:total_questions]  # Store only the first 5 questions
        session['options'] = [options] * total_questions
        session['answers'] = [None] * total_questions  # Initialize empty answers

    # POST request handling (user navigating through questions)
    if request.method == 'POST':
        # Retrieve the question index and user answer from the form
        question_index = int(request.form.get('question_index', 0))
        answer = request.form.get('answer')

        # Update the current answer in the session
        session['answers'][question_index] = answer

        # Navigation handling
        if 'next' in request.form and question_index < total_questions - 1:
            question_index += 1
        elif 'back' in request.form and question_index > 0:
            question_index -= 1
        elif 'submit' in request.form:
            # Calculate the feedback and score if on the last question
            total_score = sum(1 if a == "Always" else (0.5 if a == "Often" else 0) for a in session['answers'])
            feedback = provide_feedback(total_score, total_questions)
            return render_template('self_assessment.html', score=total_score, feedback=feedback, questions=session['questions'])

        # Redirect to the same page with updated question index
        return redirect(url_for('self_assessment', question_index=question_index))

    # Displaying the current question (GET request or after redirection)
    question_index = int(request.args.get('question_index', 0))
    question = session['questions'][question_index]
    question_options = session['options'][question_index]

    return render_template(
        'self_assessment.html',
        question=question,
        options=question_options,
        question_index=question_index,
        total_questions=total_questions
    )

def provide_feedback(score, total):
    # Feedback based on score percentage
    percentage = (score / total) * 100
    if percentage == 100:
        return "Excellent! You have a great understanding of mental health."
    elif percentage >= 80:
        return "Very Good! Keep up the good work!"
    elif percentage >= 50:
        return "Good job! Consider improving your knowledge in some areas."
    else:
        return "It looks like you might benefit from additional resources on mental health."

def get_user_data(user_id):
    """Fetch user data from the database by user ID."""
    user = User.query.get(user_id)  # Retrieve user by ID
    if user:
        return {
            'username': user.username,
            'points': user.points,
            'actions': user.actions
        }
    return None  # Return None if the user doesn't exist

# Example usage in a route
@app.route('/user/<int:user_id>', methods=['GET'])
def user_profile(user_id):
    user_data = get_user_data(user_id)
    if user_data:
        return user_data, 200  # Return user data with a 200 OK status
    return {'error': 'User not found'}, 404  # Return an error if user not found

def recommend_resources(query):
    prompt = f"Based on the user's input '{query}', recommend at least three distinct and helpful resources related to mental health. Please format them as a numbered list for clarity."

    try:
        response = cohere_client.generate(
            model='command-xlarge-nightly',
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )

        # Split the response into lines and process it
        recommendations = response.generations[0].text.strip().split('\n')
        
        # Filter out empty strings and format the recommendations
        recommendations = [rec.strip() for rec in recommendations if rec.strip()]

        # If less than 3 recommendations, provide placeholders or additional logic as needed
        while len(recommendations) < 3:
            recommendations.append("Additional recommendation placeholder.")

        return recommendations[:3]  # Return only the first 3 recommendations if more are provided

    except Exception as e:
        return [f"Error generating recommendations: {str(e)}"]

@app.route('/translate', methods=['POST'])
def translate():
    text = request.form['text']
    target_language = request.form['language']
    translation = get_translation_from_cohere(text, target_language)
    return translation

def get_translation_from_cohere(text, target_language):
    try:
        # Use a valid model name available in your Cohere account
        response = cohere_client.generate(
            model='command-xlarge-nightly',  # Replace with a valid model ID
            prompt=f"Translate the following text to {target_language}: {text}",
            max_tokens=150,
            temperature=0.7
        )
        return response.generations[0].text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/ask_question', methods=['POST'])
def ask_question():
    user_id = request.form['user_id']  # Get user_id from the request form
    question = request.form['message']   # Get the question from the request form

    # Process the question (e.g., send to AI model)
    # Save the question to the database
    new_question = Question(user_id=user_id, content=question)
    db.session.add(new_question)
    db.session.commit()
    
    # Optionally update points if needed
    # update_points(user_id, 10)
    
    return jsonify(success=True)



def update_points(user_id, points):
    user_data = get_user_data(user_id)  # Function to get user data from your database
    user_data['points'] += points
    save_user_data(user_id, user_data)  # Function to save updated data

def save_user_data(user_id, points=None, actions=None):
    """Save or update user data in the database."""
    user = User.query.get(user_id) 
    if user:
        if points is not None:
            user.points += points  
        if actions is not None:
            user.actions = actions  
        
        db.session.commit()  
        return True  
    return False  

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    rating = request.form['rating']
    comments = request.form['comments']
    # Store feedback in database (or print to console for testing)
    print(f"Feedback received: Rating = {rating}, Comments = {comments}")
    return redirect(url_for('thank_you'))

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        # Handle the feedback submission
        rating = request.form['rating']
        comments = request.form['comments']
        # You might want to save this feedback to a database or process it
        return redirect(url_for('thank_you'))
    return render_template('feedback.html')

@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/set_language', methods=['POST'])
def set_language():
    selected_language = request.form['language']
    session['language'] = selected_language
    return redirect(url_for('chat'))


@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if the user exists
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = username  # Store user info in session
            flash("Logged in successfully!", "success")  # Set flash message
            return redirect(url_for('dashboard'))  # Redirect to a protected page
        else:
            flash("Invalid username or password. Please try again.", "danger")  # Set error message
            # Render login.html without redirecting to keep the form state
            return render_template('login.html')

    return render_template('login.html')

@app.route('/get_user_id', methods=['GET'])
def get_user_id():
    username = session.get('username')
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            return jsonify({'user_id': user.id}), 200
        else:
            return jsonify({'error': 'User not found in database'}), 404
    return jsonify({'error': 'Username not in session'}), 400

# Protected dashboard route (example)
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash("You need to log in first.", "warning")
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

# Route for registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Validate if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Please choose another one.", "danger")
            return redirect(url_for('register'))
        
        # Hash the password for security
        hashed_password = generate_password_hash(password, method='sha256')
        
        # Add new user to the database
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash("You have registered successfully!", "success")
        return redirect(url_for('register'))
    # Check if a success message exists, then redirect to login if user is already registered
    if 'Registered successfully!' in [msg for cat, msg in get_flashed_messages(with_categories=True) if cat == 'success']:
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    query = request.form.get('query', '')

    return render_template('chat.html', username=session['username'])

@app.route('/generate_mental_health_questions', methods=['POST'])
def generate_mental_health_questions():
    try:
        # Prompt for generating questions
        prompt = "Generate some mental health-related questions for users:"
        response = cohere_client.generate(
            model='command-xlarge-nightly',  # Use the appropriate model
            prompt=prompt,
            max_tokens=50,  # Adjust as needed
            temperature=0.7,  # Adjust creativity
            stop_sequences=["\n"]  # Optional: specify stop sequences
        )

        questions = response.generations[0].text.strip().split('\n')  # Split into list
        return jsonify(questions)
    except Exception as e:
        app.logger.error(f"Error generating questions: {str(e)}")
        return jsonify({"error": "An error occurred while generating questions."}), 500


@app.route('/get_recommendations', methods=['POST'])
def get_recommendations():
    user_input = request.form['user_input']  # Input from user
    
    # Use Cohere to generate recommendations
    response = cohere_client.generate(
        model='command-xlarge-nightly',
        prompt=f"Based on the following user input: {user_input}\nGenerate some personalized recommendations:",
        max_tokens=150,
        temperature=0.7
    )
    
    # Check the response
    recommendations = response.generations[0].text.strip().split('\n')
    return render_template('recommendations.html', recommendations=recommendations)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']

        # Update user information
        if user:
            user.username = new_username
            user.password = new_password  # Remember to hash the password
            db.session.commit()
            session['username'] = new_username  # Update the session variable
            return redirect(url_for('chat'))

    return render_template('profile.html', username=user.username)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@socketio.on('message')
def handle_message(data):
    user_id = data['user_id']  # Get user_id from the received data
    message = data['message']   # Get the message from the received data

    # Call a new function to handle saving the question
    save_question_to_db(user_id, message)
    
    response = get_response_from_cohere(message)
    send(response)

def save_question_to_db(user_id, question):
    # Save the question to the database
    new_question = Question(user_id=user_id, content=question)
    db.session.add(new_question)
    db.session.commit()

def get_response_from_cohere(msg):
    try:
        response = cohere_client.generate(
            model='command-xlarge-nightly',  # or use 'xlarge' for a more general model
            prompt=(
                    f"{msg}. List the key points below in bullet format, each on a new line:\n. The words should not exceed 600."
                ),
            max_tokens=600,
            temperature=0.5
        )
        return response.generations[0].text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/get_questions', methods=['GET'])
def get_questions():
    user_id = request.args.get('user_id')
    if user_id:
        # Fetch questions for the user_id
        questions = Question.query.filter_by(user_id=user_id).all()
        questions_list = [question.content for question in questions]  # Use 'content' instead of 'question_text'
        return jsonify(questions_list)  # Return the list of questions as JSON
    return jsonify({'error': 'User ID not provided'}), 400

if __name__ == '__main__':
    socketio.run(app, debug=True)
