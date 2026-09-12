console.log("CampusFlow JavaScript is working!");

const API_URL = "https://campusflow-api-teua.onrender.com";

async function loadServices() {
    const response = await fetch(`${API_URL}/services`);

    const data = await response.json();

    console.log("Services received:", data);

    const serviceDropdown = document.getElementById("service");
    const staffServiceDropdown = document.getElementById("staff-service");

    serviceDropdown.innerHTML = '<option value="">Choose a service</option>';
    staffServiceDropdown.innerHTML = '<option value="">Choose a service</option>';

    data.services.forEach(service => {
        const studentOption = document.createElement("option");

        studentOption.value = service.id;
        studentOption.textContent = service.name;

        serviceDropdown.appendChild(studentOption);


        const staffOption = document.createElement("option");

        staffOption.value = service.id;
        staffOption.textContent = service.name;

        staffServiceDropdown.appendChild(staffOption);
    });
}

loadServices();

document.getElementById("join-queue-btn").addEventListener("click", submitRequest);

async function submitRequest() {
    const serviceId = document.getElementById("service").value;
    const reason = document.getElementById("reason").value;

    const response = await fetch(`${API_URL}/requests`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            service_id: Number(serviceId),
            reason: reason
        })
    });

    const data = await response.json();

    console.log("Request created:", data);

    document.getElementById("token").textContent = data.token;
    document.getElementById("status").textContent = data.status;
    document.getElementById("cancel-request-btn").dataset.requestId = data.request_id;

    const queueResponse = await fetch(`${API_URL}/queue/${serviceId}`);
    const queueData = await queueResponse.json();

    const currentRequest = queueData.queue.find(
        request => request.token === data.token
    );

    if (currentRequest) {
        document.getElementById("people-ahead").textContent =
            currentRequest.people_ahead;
    }
}

document.getElementById("cancel-request-btn").addEventListener("click", cancelRequest);

async function cancelRequest() {
    const requestId = document.getElementById("cancel-request-btn").dataset.requestId;

    if (!requestId) {
        alert("No active request to cancel.");
        return;
    }

    const response = await fetch(
        `${API_URL}/requests/${requestId}/cancel`,
        {
            method: "PATCH"
        }
    );

    const data = await response.json();

    console.log("Request cancelled:", data);

    document.getElementById("status").textContent = data.status;
    document.getElementById("people-ahead").textContent = "-";

    document.getElementById("cancel-request-btn").dataset.requestId = "";
}

document.getElementById("serve-next-btn").addEventListener("click", serveNext);

async function serveNext() {
    const serviceId = document.getElementById("staff-service").value;

    const response = await fetch(`${API_URL}/queue/${serviceId}/next`, {
        method: "POST"
    });

    const data = await response.json();

    document.getElementById("staff-token").textContent = data.token;
    document.getElementById("staff-reason").textContent = data.reason;
    document.getElementById("staff-priority").textContent = data.priority;
    document.getElementById("complete-btn").dataset.requestId = data.id;

    await loadQueue();
}

document.getElementById("complete-btn").addEventListener("click", completeRequest);

async function completeRequest() {
    const completeButton = document.getElementById("complete-btn");
    const requestId = completeButton.dataset.requestId;

    const response = await fetch(`${API_URL}/queue/${requestId}/complete`, {
        method: "PATCH"
    });

    const data = await response.json();

    console.log("Request completed:", data);

    document.getElementById("staff-token").textContent = "-";
    document.getElementById("staff-reason").textContent = "-";
    document.getElementById("staff-priority").textContent = "-";

    completeButton.dataset.requestId = "";

    await loadQueue();
}

async function loadQueue() {
    const serviceId = document.getElementById("staff-service").value;

    if (!serviceId) {
        return;
    }

    const response = await fetch(`${API_URL}/queue/${serviceId}`);
    const data = await response.json();

    const queueList = document.getElementById("queue-list");

    queueList.innerHTML = "<h3>Waiting Queue</h3>";

    const servingRequest = data.queue.find(
        request => request.status === "Serving"
    );

    if (servingRequest) {
        document.getElementById("staff-token").textContent =
            servingRequest.token;

        document.getElementById("staff-reason").textContent =
            servingRequest.reason;

        document.getElementById("staff-priority").textContent =
            servingRequest.priority;

        document.getElementById("complete-btn").dataset.requestId =
            servingRequest.id;
    
    }

    const waitingRequests = data.queue.filter(
        request => request.status === "Waiting"
    );

    waitingRequests.forEach(request => {
        const queueItem = document.createElement("div");

        queueItem.innerHTML = `
            <p><strong>${request.token}</strong></p>
            <p>Reason: ${request.reason}</p>

            <label>Priority:</label>
            <select class="priority-select" data-request-id="${request.id}">
                <option value="Normal" ${request.priority === "Normal" ? "selected" : ""}>Normal</option>
                <option value="High" ${request.priority === "High" ? "selected" : ""}>High</option>
                <option value="Urgent" ${request.priority === "Urgent" ? "selected" : ""}>Urgent</option>
            </select>

            <p>Status: ${request.status}</p>
            <hr>
        `;

        queueList.appendChild(queueItem);
    });

    const prioritySelects = document.querySelectorAll(".priority-select");

    prioritySelects.forEach(select => {
        select.addEventListener("change", () => {
            updatePriority(select.dataset.requestId, select.value);
        });
    });
}
document.getElementById("staff-service").addEventListener("change", loadQueue);

async function updatePriority(requestId, priority) {
    const response = await fetch(
        `${API_URL}/requests/${requestId}/priority?priority=${priority}`,
        {
            method: "PATCH"
        }
    );

    const data = await response.json();

    console.log("Priority updated:", data);

    await loadQueue();
}