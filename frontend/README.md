# AnimePahe Web Downloader - Frontend

This is the frontend for the AnimePahe Web Downloader, built with Vite.

## Setup

1.  Install dependencies:
    ```bash
    npm install
    ```

## Development

1.  Start the backend server (in the root directory):
    ```bash
    python web/main.py
    ```
    This will start the API server on `http://localhost:8000`.

2.  Start the frontend development server (in this directory):
    ```bash
    npm run dev
    ```
    This will start the Vite server (usually on `http://localhost:5173`).
    The frontend will proxy API requests to the backend.

## Production Build

To build the frontend for production:

```bash
npm run build
```

This will create a `dist` directory. The Python backend is configured to serve files from this directory if it exists.
