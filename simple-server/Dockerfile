# Use an official Node.js runtime as a parent image.
# Using alpine for a smaller image size.
FROM node:18-alpine
# Set the working directory in the container.

# Copy package.json and package-lock.json (if available) to the working directory.
# The wildcard `package*.json` is used to copy both files.
COPY package*.json ./

# Install application dependencies. This is done in a separate layer
# to take advantage of Docker's layer caching.
RUN npm install

# Copy the rest of the application source code.
COPY . .

# Expose the application port for internal communication.
EXPOSE 3000

# Define the command to run the application.
CMD [ "npm", "start" ]