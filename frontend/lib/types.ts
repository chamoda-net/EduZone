// Shapes returned by the EduZone API (/api/v1). Money is integer cents plus currency.

export type Branding = {
  name: string;
  slug: string;
  logo_url: string | null;
  primary_color: string | null;
};

export type Role = "owner" | "admin" | "teacher" | "student";

export type Me = {
  user_id: string;
  member_id: string;
  full_name: string;
  phone: string | null;
  role: Role;
  preferred_language: string;
};

export type PricingModel = "monthly" | "one_time" | "free";
export type ClassStatus = "draft" | "published" | "archived";
export type MonthStatus = "upcoming" | "open" | "closed";
export type LessonType = "live" | "recorded" | "document";

export type ClassItem = {
  id: string;
  teacher_member_id: string;
  title: string;
  slug: string;
  description: string | null;
  subject: string | null;
  exam: "grade_5" | "ol" | "al" | "other" | null;
  batch_year: number | null;
  medium: "si" | "ta" | "en" | null;
  cover_image_url: string | null;
  pricing_model: PricingModel;
  monthly_fee_cents: number | null;
  one_time_price_cents: number | null;
  currency: string;
  allow_late_months: boolean;
  max_video_views: number | null;
  status: ClassStatus;
  created_at: string;
  updated_at: string;
};

export type ClassPage = { items: ClassItem[]; next_cursor: string | null };

export type Month = {
  id: string;
  class_id: string;
  month_start: string; // YYYY-MM-01
  fee_cents: number | null;
  effective_fee_cents: number;
  currency: string;
  status: MonthStatus;
  created_at: string;
};

export type Lesson = {
  id: string;
  class_id: string;
  class_month_id: string | null;
  title: string;
  description: string | null;
  lesson_type: LessonType;
  sort_order: number;
  scheduled_at: string | null;
  duration_minutes: number | null;
  zoom_join_url: string | null;
  is_free_preview: boolean;
  is_published: boolean;
  created_at: string;
  updated_at: string;
};
