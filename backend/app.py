from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def entrypoint():
    return "<h1> Successfully Ran flask app ;^) </h1>"

@app.route('/api/data')
def getTestData():
    print('Testin')
    return jsonify({"message": "Hello from Steven!", "status": "success"})

# TODO: Once this does work, change it to the proxy in package.json
#       in your frontend
# TODO: This isn't working
if __name__ == '__main__':
    app.run(port=5001, debug=True)