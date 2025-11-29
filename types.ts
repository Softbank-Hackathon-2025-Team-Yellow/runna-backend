export enum Runtime {
  PYTHON = 'python',
  NODEJS = 'nodejs'
}

export enum ExecutionType {
  SYNC = 'sync',
  ASYNC = 'async'
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed'
}

export interface Function {
  name: string;
  runtime: Runtime;
  code: string;
  execution_type: ExecutionType;
}

export interface Job {
  job_id: number;
  status: JobStatus;
  result?: any;
  timestamp: string;
}

export interface CommonApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

export type SuccessResponse<T = any> = CommonApiResponse<T> & {
  success: true;
  data: T;
}

export type ErrorResponse = CommonApiResponse<never> & {
  success: false;
  error: {
    code: string;
    message: string;
    details?: any;
  };
}

export type ApiResponse<T = any> = SuccessResponse<T> | ErrorResponse;