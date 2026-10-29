import nodemailer from "nodemailer";

const user = process.env.SMTP_USER;
const pass = process.env.SMTP_PASS;
const host = process.env.SMTP_HOST;
const port = parseInt(process.env.SMTP_PORT || "587", 10);

export const mailConfigured = !!(user && pass);

const transporter = mailConfigured
  ? nodemailer.createTransport(
      host
        ? { host, port, secure: port === 465, auth: { user, pass } }
        : { service: "gmail", auth: { user: user as string, pass: pass as string } },
    )
  : null;

export async function sendResetLink(to: string, resetUrl: string, ttlMinutes: number): Promise<boolean> {
  if (!transporter) return false;
  await transporter.sendMail({
    from: process.env.SMTP_FROM || `IT Learning <${user}>`,
    to,
    subject: "IT Learning — Link đặt lại mật khẩu",
    text:
      `Bạn (hoặc ai đó dùng email của bạn) vừa yêu cầu đặt lại mật khẩu IT Learning.\n\n` +
      `Link đặt lại (tối đa ${ttlMinutes} phút, dùng một lần):\n${resetUrl}\n\n` +
      `Nếu không phải bạn yêu cầu, hãy bỏ qua email này — mật khẩu của bạn không thay đổi.`,
    html:
      `<p>Bạn vừa yêu cầu đặt lại mật khẩu tại <b>IT Learning</b>.</p>` +
      `<p><a href="${resetUrl}">Đặt lại mật khẩu</a> (tối đa ${ttlMinutes} phút, dùng một lần).</p>` +
      `<p>Nếu không phải bạn yêu cầu, hãy bỏ qua email này — mật khẩu của bạn không thay đổi.</p>`,
  });
  return true;
}
