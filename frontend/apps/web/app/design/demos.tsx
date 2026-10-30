"use client";

import { Bell } from "lucide-react";

import { Button, Dialog, DialogClose, Field, Input, toast } from "@eduzone/ui";

// Interactive pieces of the style guide (dialog, toasts). Text here is sample copy, not UI.
export function DialogDemo() {
  return (
    <Dialog
      trigger={<Button variant="secondary">Open dialog</Button>}
      title="Ask the teacher"
      description="Request access to October 2026. The teacher will approve or decline."
    >
      <div className="flex flex-col gap-4">
        <Field label="Message (optional)">
          <Input placeholder="I joined late because…" />
        </Field>
        <div className="flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="ghost">Cancel</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button onClick={() => toast("Request sent to the teacher")}>Send request</Button>
          </DialogClose>
        </div>
      </div>
    </Dialog>
  );
}

export function ToastDemo() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="secondary" icon={<Bell className="size-4" />} onClick={() => toast("Lesson saved")}>
        Success toast
      </Button>
      <Button variant="danger" onClick={() => toast("Couldn't reach the server. Try again.", "error")}>
        Error toast
      </Button>
    </div>
  );
}
