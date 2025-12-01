import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface DockerContainer {
  id: string;
  name: string;
  image: string;
  status: string;
  ports: string;
}

export interface DockerImage {
  repository: string;
  tag: string;
  id: string;
  created: string;
  size: string;
}

export async function getContainers(): Promise<DockerContainer[]> {
  try {
    const { stdout } = await execAsync('docker ps -a --format "table {{.ID}}\\t{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}"');
    const lines = stdout.trim().split('\n').slice(1); // Skip header

    return lines.map(line => {
      const [id, name, image, status, ports] = line.split('\t');
      return { id, name, image, status, ports };
    });
  } catch (error) {
    console.error('Failed to get containers:', error);
    return [];
  }
}

export async function getImages(): Promise<DockerImage[]> {
  try {
    const { stdout } = await execAsync('docker images --format "table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.CreatedAt}}\\t{{.Size}}"');
    const lines = stdout.trim().split('\n').slice(1); // Skip header

    return lines.map(line => {
      const [repository, tag, id, created, size] = line.split('\t');
      return { repository, tag, id, created, size };
    });
  } catch (error) {
    console.error('Failed to get images:', error);
    return [];
  }
}

export async function startContainer(containerName: string): Promise<boolean> {
  try {
    await execAsync(`docker start ${containerName}`);
    return true;
  } catch (error) {
    console.error(`Failed to start container ${containerName}:`, error);
    return false;
  }
}

export async function stopContainer(containerName: string): Promise<boolean> {
  try {
    await execAsync(`docker stop ${containerName}`);
    return true;
  } catch (error) {
    console.error(`Failed to stop container ${containerName}:`, error);
    return false;
  }
}

export async function restartContainer(containerName: string): Promise<boolean> {
  try {
    await execAsync(`docker restart ${containerName}`);
    return true;
  } catch (error) {
    console.error(`Failed to restart container ${containerName}:`, error);
    return false;
  }
}

export async function getContainerLogs(containerName: string, lines: number = 100): Promise<string> {
  try {
    const { stdout } = await execAsync(`docker logs --tail ${lines} ${containerName}`);
    return stdout;
  } catch (error) {
    console.error(`Failed to get logs for container ${containerName}:`, error);
    return '';
  }
}

export async function restartDockerContainers(): Promise<{
  stdout: string;
  stderr: string;
  command: string;
  composeDir: string;
}> {
  try {
    // Get the compose directory (usually the project root)
    const composeDir = process.cwd();

    // Run docker-compose restart to restart all containers
    const command = 'docker-compose restart';
    const { stdout, stderr } = await execAsync(command, { cwd: composeDir });

    return {
      stdout: stdout || '',
      stderr: stderr || '',
      command,
      composeDir,
    };
  } catch (error: any) {
    console.error('Failed to restart docker containers:', error);
    throw {
      stdout: '',
      stderr: error?.stderr || error?.message || 'Unknown error',
      command: 'docker-compose restart',
      composeDir: process.cwd(),
    };
  }
}

export async function isDockerRunning(): Promise<boolean> {
  try {
    await execAsync('docker info');
    return true;
  } catch (error) {
    return false;
  }
}
