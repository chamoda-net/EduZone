// EduZone component kit (FRONTEND.md section 9). Mobile-first: 44px touch targets, colours only
// from tokens (tokens.css). Client-only pieces live in their own files with "use client".

/** What a form Server Action returns to its form (errors are already translated). */
export type ActionState = { error?: string; ok?: boolean; at?: number };

export { cx, hashString } from "./cx";
export { Button, Spinner, buttonClass, buttonStyles, type ButtonSize, type ButtonVariant } from "./button";
export { Checkbox, Field, Input, Select, Textarea, inputClass } from "./forms";
export { Badge, StatusPill, type BadgeTone, type PillState } from "./badge";
export {
  Alert,
  Card,
  CardTitle,
  Container,
  DataList,
  EmptyState,
  ErrorText,
  PageHeader,
  Skeleton,
  StatTile,
} from "./surfaces";
export { ClassCover } from "./cover";
export { Avatar, Logo, LogoMark, initials } from "./identity";
export { FilterChips, type Chip } from "./chips";
export { Dialog, DialogClose } from "./dialog";
export { Toaster, toast } from "./toast";
export { HeaderNav, NavDrawer, SideNav, TabBar, type NavItem } from "./nav";
export { ConsoleFrame } from "./console";
export { CodeInput, PasswordInput } from "./inputs";
