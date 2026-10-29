import Link from "next/link";

import { Card, buttonClass } from "@/components/ui";
import { t } from "@/lib/i18n";

import { createTenant } from "../../../actions";
import { TenantForm } from "../../tenant-form";

export default function NewTenantPage() {
  return (
    <>
      <Link href="/platform" className={`${buttonClass.link} text-sm`}>← {t("platform.back")}</Link>
      <h1 className="text-2xl font-semibold">{t("platform.tenants.new")}</h1>
      <Card>
        <TenantForm action={createTenant} />
      </Card>
    </>
  );
}
