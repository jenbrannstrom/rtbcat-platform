/**
 * Layout for login page - no sidebar, no authenticated layout wrapper.
 */
export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
