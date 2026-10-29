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

export type MediaKind = "video" | "document";
export type MediaStatus = "uploading" | "processing" | "ready" | "failed";

export type Media = {
  id: string;
  kind: MediaKind;
  name: string;
  mime_type: string | null;
  size_bytes: number;
  duration_seconds: number | null;
  status: MediaStatus;
  created_at: string;
};

export type MediaPage = { items: Media[]; next_cursor: string | null };

export type VideoUpload = {
  media: Media;
  upload: { endpoint: string; headers: Record<string, string>; expires_at: string };
};

export type Preview = { url: string; expires_at: string };

export type LessonResource = {
  id: string;
  lesson_id: string;
  title: string | null;
  sort_order: number;
  is_downloadable: boolean;
  media: Media;
};

// --- student side (step 6) ----------------------------------------------------------

export type PublicClass = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  subject: string | null;
  exam: ClassItem["exam"];
  batch_year: number | null;
  medium: ClassItem["medium"];
  cover_image_url: string | null;
  pricing_model: PricingModel;
  monthly_fee_cents: number | null;
  one_time_price_cents: number | null;
  currency: string;
  teacher_name: string;
};

export type PublicClassPage = { items: PublicClass[]; next_cursor: string | null };

export type PublicMonth = { id: string; month_start: string; fee_cents: number; currency: string; status: MonthStatus };

export type PublicLesson = {
  id: string;
  class_month_id: string | null;
  title: string;
  lesson_type: LessonType;
  sort_order: number;
  scheduled_at: string | null;
  duration_minutes: number | null;
  is_free_preview: boolean;
};

export type PublicClassDetail = { class: PublicClass; months: PublicMonth[]; lessons: PublicLesson[] };

export type MonthAccess =
  | "granted"
  | "buy"
  | "upcoming"
  | "request"
  | "pending"
  | "approved"
  | "rejected"
  | "unavailable";

export type StudentMonth = PublicMonth & { access: MonthAccess };
export type StudentLesson = PublicLesson & { unlocked: boolean };

export type StudentClassView = {
  class: PublicClass;
  enrolled: boolean;
  has_class_access: boolean;
  months: StudentMonth[];
  lessons: StudentLesson[];
};

export type MyClass = { class: PublicClass; enrolled_at: string; unlocked_months: number };

export type StudentResource = {
  id: string;
  title: string;
  kind: MediaKind;
  duration_seconds: number | null;
  is_downloadable: boolean;
  ready: boolean;
  views_used: number;
  views_allowed: number | null;
};

export type StudentLessonDetail = StudentLesson & {
  class_id: string;
  class_slug: string;
  class_title: string;
  description: string | null;
  zoom_join_url: string | null;
  resources: StudentResource[];
};

export type OpenResource = {
  kind: MediaKind;
  url: string;
  expires_at: string;
  watermark: { name: string; phone: string | null };
  views_used: number | null;
  views_allowed: number | null;
};

// --- organization: students and requests ---------------------------------------------

export type GrantInfo = { id: string; source: "purchase" | "manual" | "free" | "scholarship"; granted_at: string };

export type ClassStudent = {
  member_id: string;
  full_name: string;
  phone: string | null;
  enrollment_status: "active" | "left" | "removed" | null;
  enrolled_at: string | null;
  access: GrantInfo | null;
};

export type LateRequest = {
  id: string;
  status: "pending" | "approved" | "rejected" | "fulfilled" | "expired";
  student_member_id: string;
  student_name: string;
  student_phone: string | null;
  class_id: string;
  class_title: string;
  class_month_id: string;
  month_start: string;
  student_note: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
};

// --- payments (step 7) ----------------------------------------------------------------

export type OrderStatus = "pending" | "paid" | "failed" | "cancelled" | "refunded" | "partially_refunded";

export type Order = {
  id: string;
  order_no: string;
  status: OrderStatus;
  currency: string;
  total_cents: number;
  created_at: string;
  paid_at: string | null;
  method: string | null;
  card_last4: string | null;
  item: {
    id: string;
    class_id: string;
    class_slug: string;
    class_month_id: string | null;
    description: string;
    amount_cents: number;
  };
};

export type GatewayRedirect = { method: "GET" | "POST"; url: string; fields: Record<string, string> };
export type CheckoutResult = { order: Order; redirect: GatewayRedirect };

export type OrgOrder = Order & { student_name: string; student_phone: string | null };
export type OrgOrderPage = { items: OrgOrder[]; next_cursor: string | null };

// --- money (step 8) -----------------------------------------------------------------

export type CashflowFigures = {
  gross_sales_cents: number;
  refunds_cents: number;
  gateway_fees_cents: number;
  commission_cents: number;
  net_cents: number;
  paid_out_cents: number;
};

export type Cashflow = {
  currency: string;
  commission_bps: number;
  gateway_fee_bearer: "tenant" | "platform";
  balance_due_cents: number;
  months: (CashflowFigures & { month: string })[];
  totals: CashflowFigures;
};

export type TeacherEarning = {
  teacher_member_id: string;
  teacher_name: string;
  sales_count: number;
  gross_sales_cents: number;
  refunds_cents: number;
  commission_cents: number;
  net_cents: number;
};

export type Earnings = { month: string; currency: string; teachers: TeacherEarning[]; total_net_cents: number };
