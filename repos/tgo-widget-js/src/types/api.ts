// Types for API contract (derived from docs/api.json)

export type VisitorSystemInfo = {
  source_detail?: string | null
  browser?: string | null
  operating_system?: string | null
}


export type VisitorRegisterRequest = {
  platform_api_key: string
  name?: string | null
  nickname?: string | null
  avatar_url?: string | null
  phone_number?: string | null
  email?: string | null
  company?: string | null
  job_title?: string | null
  source?: string | null
  note?: string | null
  custom_attributes?: Record<string, string | null>
  system_info?: VisitorSystemInfo | null
  timezone?: string | null  // 访客时区，如 "Asia/Shanghai"
}

export type VisitorRegisterResponse = {
  id: string
  platform_open_id: string
  project_id: string
  platform_id: string
  created_at: string
  updated_at: string
  first_visit_time: string
  last_visit_time: string
  last_offline_time?: string | null
  is_online: boolean
  // Messaging
  channel_id: string
  channel_type?: number // 1=person, 2=group, 251=special customer service (see docs)
  im_token?: string // WuKongIM authentication token
  // Optional profile fields
  name?: string | null
  nickname?: string | null
  avatar_url?: string | null
  phone_number?: string | null
  email?: string | null
  company?: string | null
  job_title?: string | null
  source?: string | null
  note?: string | null
  custom_attributes?: Record<string, string | null>
}

export type CachedVisitor = {
  apiBase: string
  platform_api_key: string
  visitor_id: string
  platform_open_id: string
  channel_id: string
  channel_type?: number
  im_token?: string // WuKongIM authentication token
  project_id: string
  platform_id: string
  created_at: string
  updated_at: string
  // Optional expiry epoch millis if needed later
  expires_at?: number
}

