import { exec } from 'child_process';
import { promisify } from 'util';
import { promises as fs } from 'fs';
import * as path from 'path';

const execAsync = promisify(exec);

interface RestartResult {
  stdout: string;
  stderr: string;
  command: string;
  composeDir: string;
}

/**
 * Finds the docker-compose.yml file and returns its directory
 */
async function findComposeFile(): Promise<string> {
  // Check if running inside Docker container
  const inContainer = process.env.DOCKER_CONTAINER || process.env.ENV_FILE_PATH;
  
  // Possible locations for docker-compose.yml
  const possiblePaths: string[] = [];
  
  // Check environment variable first (highest priority)
  if (process.env.COMPOSE_FILE_PATH) {
    possiblePaths.push(process.env.COMPOSE_FILE_PATH);
  }
  
  // Inside container (mounted from host) - this is the most likely location
  possiblePaths.push('/app/comfy-bridge/docker-compose.yml');
  
  // Windows host path
  if (process.platform === 'win32') {
    possiblePaths.push('c:\\dev\\comfy-bridge\\docker-compose.yml');
  }
  
  // Relative to current working directory
  possiblePaths.push(
    path.join(process.cwd(), 'docker-compose.yml'),
    path.join(process.cwd(), '..', 'docker-compose.yml'),
    path.join(process.cwd(), '..', '..', 'docker-compose.yml'),
  );
  
  // Common Linux/Mac paths
  possiblePaths.push('/app/docker-compose.yml');

  // Try each path
  for (const composePath of possiblePaths) {
    try {
      const normalizedPath = path.normalize(composePath);
      await fs.access(normalizedPath);
      console.log(`Found docker-compose.yml at: ${normalizedPath}`);
      // Found it! Return the directory containing the file
      return path.dirname(normalizedPath);
    } catch (error) {
      // File doesn't exist at this path, try next
      continue;
    }
  }

  // If not found, try to find it by searching from common parent directories
  const searchPaths = [
    '/app/comfy-bridge',
    '/app',
    process.cwd(),
    path.join(process.cwd(), '..'),
    path.join(process.cwd(), '..', '..'),
  ];

  for (const searchPath of searchPaths) {
    try {
      const composePath = path.join(searchPath, 'docker-compose.yml');
      await fs.access(composePath);
      console.log(`Found docker-compose.yml at: ${composePath}`);
      return searchPath;
    } catch {
      continue;
    }
  }

  // Log all attempted paths for debugging
  console.error('Failed to find docker-compose.yml. Searched paths:', possiblePaths);
  console.error('Current working directory:', process.cwd());
  console.error('Environment:', {
    DOCKER_CONTAINER: process.env.DOCKER_CONTAINER,
    ENV_FILE_PATH: process.env.ENV_FILE_PATH,
    COMPOSE_FILE_PATH: process.env.COMPOSE_FILE_PATH,
  });

  throw new Error(
    `docker-compose.yml not found. Searched in: ${possiblePaths.join(', ')}`
  );
}

/**
 * Restarts Docker containers using docker compose
 */
export async function restartDockerContainers(): Promise<RestartResult> {
  const composeDir = await findComposeFile();
  const composeFile = path.join(composeDir, 'docker-compose.yml');

  // Verify the file exists and is readable
  let absoluteComposeFile: string;
  try {
    // Normalize the path - use absolute path to avoid issues
    absoluteComposeFile = path.isAbsolute(composeFile) 
      ? composeFile 
      : path.resolve(composeDir, composeFile);
    
    // Verify file exists and is readable
    await fs.access(absoluteComposeFile);
    
    // Try to read a bit of the file to ensure it's accessible
    const stats = await fs.stat(absoluteComposeFile);
    if (!stats.isFile()) {
      throw new Error(`${absoluteComposeFile} exists but is not a file`);
    }
    
    console.log(`Using docker-compose.yml at: ${absoluteComposeFile}`);
    console.log(`Working directory: ${composeDir}`);
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error(`Error accessing docker-compose.yml at ${composeFile}:`, errorMsg);
    throw new Error(
      `docker-compose.yml not accessible at ${composeFile}: ${errorMsg}`
    );
  }

  // Try docker compose (newer) first, then docker-compose (legacy)
  // Use absolute path with -f flag to ensure docker-compose can find it
  // Use --project-directory to ensure relative paths in compose file resolve correctly
  // Use 'up -d' instead of 'restart' to recreate containers with new env vars
  const commands = [
    `docker compose -f "${absoluteComposeFile}" --project-directory "${composeDir}" up -d`,
    `docker-compose -f "${absoluteComposeFile}" --project-directory "${composeDir}" up -d`,
    // Try without --project-directory as fallback
    `docker compose -f "${absoluteComposeFile}" up -d`,
    `docker-compose -f "${absoluteComposeFile}" up -d`,
    // Fallback to restart if up -d doesn't work
    `docker compose -f "${absoluteComposeFile}" --project-directory "${composeDir}" restart`,
    `docker-compose -f "${absoluteComposeFile}" --project-directory "${composeDir}" restart`,
  ];

  let lastError: Error | null = null;

  for (const command of commands) {
    try {
      console.log(`Attempting: ${command} in directory: ${composeDir}`);
      
      // Execute in the compose directory to ensure relative paths in docker-compose.yml work
      // Set COMPOSE_FILE environment variable as well
      const { stdout, stderr } = await execAsync(command, {
        cwd: composeDir,
        env: {
          ...process.env,
          COMPOSE_FILE: absoluteComposeFile,
          COMPOSE_PROJECT_NAME: 'comfy-bridge',
        },
        // Increase timeout for container restart operations
        timeout: 60000, // 60 seconds
      });

      return {
        stdout,
        stderr,
        command,
        composeDir,
      };
    } catch (error: any) {
      lastError = error;
      // If this command failed, try the next one
      console.warn(`Command failed: ${command}`, error.message);
      if (error.stderr) {
        console.warn('Error stderr:', error.stderr);
      }
      continue;
    }
  }

  // Both commands failed
  const errorMessage = lastError?.message || 'Unknown error';
  const errorStderr = (lastError as any)?.stderr || errorMessage;
  
  // Create a proper error object
  const restartError: any = new Error(`Failed to restart containers: ${errorMessage}`);
  restartError.stderr = errorStderr;
  restartError.command = commands.join(' OR ');
  restartError.composeDir = composeDir;
  
  throw restartError;
}
