## LMCP Dashboard Runtime

Official frontend runtime for this task: `lmcp-dashboard`

### Runtime

- framework: Next.js
- dev port: `3000`
- dev command: `npm run dev`
- production start command: `npm run start`

### Required environment variables

Create a local env file:

```bash
cp .env.example .env.local
```

Variables:

- `NEXT_PUBLIC_API_BASE_URL`
  - backend base URL used by the dashboard
  - default: `http://127.0.0.1:8000`
- `NEXT_PUBLIC_APP_ENV`
  - frontend environment label shown in the dashboard
  - default: `development`

### Startup

Install dependencies:

```bash
npm install
```

Start the dashboard:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

### API URL Configuration

The dashboard uses `NEXT_PUBLIC_API_BASE_URL` for backend requests.

Current backend endpoints used by the dashboard:

- `GET /dashboard`
- `POST /refresh/all`
- `GET /health`

### Health Surface

The dashboard exposes a lightweight runtime indicator on the main page:

- backend connectivity indicator
- backend URL indicator
- environment indicator
- backend health timestamp when available

### Hardcoded Backend URLs Removed

The following hardcoded backend API base URL was replaced with environment configuration:

- `http://127.0.0.1:8000` in `app/page.tsx`

---

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
