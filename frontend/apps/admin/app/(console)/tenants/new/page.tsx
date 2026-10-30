import Link from "next/link";

import { Card, buttonClass } from "@eduzone/ui";
import { t } from "@eduzone/lib/i18n";

import { createTenant } from "../../../actions";
import { TenantForm } from "../../tenant-form";

export default function NewTenantPage() {
  return (
    <>
      <Link href="/" className={`${buttonClass.link} text-sm`}>← {t("platform.back")}</Link>
      <h1 className="font-display text-3xl font-semibold sm:text-4xl">{t("platform.tenants.new")}</h1>
      <Card>
        <TenantForm action={createTenant} />
      </Card>
    </>
  );
}
