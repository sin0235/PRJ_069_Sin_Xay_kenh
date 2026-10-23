import { redirect } from "next/navigation";
import { cookies } from "next/headers";

export default async function Home() {
  const cookieStore = await cookies();
  const token = cookieStore.get("baha_auth_token")?.value;
  if (token) {
    redirect("/dashboard");
  } else {
    redirect("/auth/v1/login");
  }
}
