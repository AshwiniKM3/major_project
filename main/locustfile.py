from locust import HttpUser, TaskSet, task, between
import random

class JoinQueueTaskSet(TaskSet):
    def on_start(self):
        # When a Locust user starts, log them in
        self.logged_in_user = None  # Initialize a variable to store the logged-in user
        self.login()

    def login(self):
        # Get the login page to retrieve the CSRF token
        response = self.client.get("/login/", headers={"Accept": "text/html"})
        csrf_token = response.cookies['csrftoken']  # Retrieve CSRF token from cookies

        # Generate random user credentials
        user_number = random.randint(1, 40)
        username = f'testuser{user_number}'
        password = f'testuser{user_number}'

        # Log in using the CSRF token
        response = self.client.post(
            "/login/",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": csrf_token
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "/login/"
            },
            cookies={"csrftoken": csrf_token}
        )

        if response.status_code == 200:
            print(f"User {username} logged in successfully.")
            # Save the logged-in username for later use when joining the queue
            self.logged_in_user = username
        else:
            print(f"Failed to log in user {username}: {response.status_code}")

    @task(1)
    def join_queue(self):
        if not self.logged_in_user:
            print("No logged-in user, skipping queue join.")
            return

        # Get the join-queue page to retrieve the CSRF token
        response = self.client.get("/join-queue/", headers={"Accept": "text/html"})
        csrf_token = response.cookies['csrftoken']  # Retrieve CSRF token from cookies

        # Only provide 'number_of_people' via form as the session has the username
        user_data = {
            "number_of_people": random.randint(1, 5),  # Choose 1 to 5 people
            "csrfmiddlewaretoken": csrf_token  # Include CSRF token
        }

        # Submit the form to join the queue using the session of the logged-in user
        response = self.client.post(
            "/join-queue/",
            data=user_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "/join-queue/"
            },
            cookies={"csrftoken": csrf_token}
        )

        if response.status_code == 200:
            print(f"User {self.logged_in_user} successfully joined queue with {user_data}")
        else:
            print(f"Failed to join queue: {response.status_code} - {response.content}")

class WebsiteUser(HttpUser):
    tasks = [JoinQueueTaskSet]
    wait_time = between(1, 5)  # Wait between 1 to 5 seconds between tasks
