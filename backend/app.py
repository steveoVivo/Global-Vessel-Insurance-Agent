from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def entrypoint():
    return "<h1> This is the Flask API. This page is not meant to be accessed. The React-App is serviced at `http://localhost:5173/` </h1>"

@app.route('/api/data')
def getTestData():
    return jsonify({"message": "If you see this message, BOTH your React AND Flask environments are working"})

# TODO: Once this does work, change it to the proxy in package.json
#       in your frontend
# TODO: This isn't working, it keeps using 5000
if __name__ == '__main__':
    app.run(port=5000, debug=True)