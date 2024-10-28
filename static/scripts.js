const socket = io();

function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value;
    if (message) {
        displayMessage(message, 'user');
        messageInput.value = ''; // Clear the input field
        document.getElementById('loading').style.display = 'block'; // Show loading animation
        socket.emit('message', message);
    }
}

socket.on('response', function(response) {
    displayMessage(response, 'bot');
    document.getElementById('loading').style.display = 'none'; // Hide loading animation
});

function displayMessage(message, sender) {
    const chatBox = document.getElementById('chatBox');
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', sender);
    messageElement.textContent = message;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to the bottom
}
