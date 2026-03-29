-- Supabase Auth Migration Script
-- Run this in your Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql) (Warning: This will delete existing employee data to reset for UUIDs)

-- 1. CLEANUP
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS handle_new_user();
DROP TABLE IF EXISTS payroll_record CASCADE;
DROP TABLE IF EXISTS leave_request CASCADE;
DROP TABLE IF EXISTS attendance CASCADE;
DROP TABLE IF EXISTS salary_structure CASCADE;
DROP TABLE IF EXISTS employee_profile CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS department CASCADE;

-- 2. CREATE TABLES (Matches SQLAlchemy Models)
CREATE TABLE public.department (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'employee'
);

CREATE TABLE public.employee_profile (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    dept_id INTEGER REFERENCES public.department(id),
    job_title VARCHAR(100),
    joining_date TIMESTAMP DEFAULT NOW(),
    contact VARCHAR(20),
    address TEXT
);

CREATE TABLE public.salary_structure (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES public.employee_profile(id) ON DELETE CASCADE,
    base_salary FLOAT DEFAULT 0.0,
    allowances FLOAT DEFAULT 0.0,
    deductions FLOAT DEFAULT 0.0
);

CREATE TABLE public.attendance (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE public.leave_request (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'Pending'
);

CREATE TABLE public.payroll_record (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    net_amount FLOAT NOT NULL,
    paid_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'Paid'
);

-- 3. AUTO-PROFILE TRIGGER
-- This function runs every time a user signs up via Supabase Auth
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, name, email, role)
  VALUES (
    NEW.id, 
    COALESCE(NEW.raw_user_meta_data->>'name', 'New Employee'), 
    NEW.email, 
    'employee' -- Default role for new signups
  );
  INSERT INTO public.employee_profile (user_id, job_title)
  VALUES (NEW.id, 'Unassigned');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create the trigger
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 4. ENABLE ROW LEVEL SECURITY (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leave_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payroll_record ENABLE ROW LEVEL SECURITY;

-- 5. POLICIES (Users can only see/edit THEIR OWN data)

-- Users Policy
CREATE POLICY "Users can view their own profile" ON public.users
    FOR SELECT USING (auth.uid() = id);

-- Attendance Policy
CREATE POLICY "Users can manage their own attendance" ON public.attendance
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Leave Requests Policy
CREATE POLICY "Users can manage their own leaves" ON public.leave_request
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Payroll Policy
CREATE POLICY "Users can view their own payroll" ON public.payroll_record
    FOR SELECT USING (auth.uid() = user_id);
