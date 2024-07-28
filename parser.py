from flask import Flask, request, jsonify
import os

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_file_and_data():
    if 'text_file' not in request.files or 'data' not in request.form:
        return jsonify({'error': 'Text file or data not provided'}), 400

    text_file = request.files['text_file']
    data = request.form['data']

    # Process the text file
    text_file_path = os.path.join('uploads', text_file.filename)
    text_file.save(text_file_path)
    with open(text_file_path, 'r') as f:
        text_content = f.read()

    # Process the dictionary
    try:
        data_dict = eval(data)  # Use ast.literal_eval() for safer conversion
    except Exception as e:
        return jsonify({'error': 'Invalid dictionary format'}), 400

    return jsonify({
        'message': 'File and data received',
        'text_file_content': text_content,
        'data': data_dict
    })

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)
