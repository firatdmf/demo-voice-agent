--
-- PostgreSQL database dump
--

-- Dumped from database version 15.10
-- Dumped by pg_dump version 15.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.applications (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    package_id uuid NOT NULL,
    team character varying(100),
    payment_type character varying(50) NOT NULL,
    delivery character varying(20) NOT NULL,
    status character varying(20),
    apply_token character varying(256),
    apply_url character varying(500),
    token_expires_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: call_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.call_sessions (
    id uuid NOT NULL,
    twilio_call_sid character varying(100),
    customer_id uuid,
    application_id uuid,
    caller_phone character varying(20),
    state_history json,
    conversation_summary text,
    flags json,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    status character varying(20)
);


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    surname character varying(100) NOT NULL,
    tckn character varying(256),
    birth_date date,
    phone character varying(20) NOT NULL,
    city character varying(100),
    district character varying(100),
    neighborhood character varying(100),
    street character varying(200),
    building_no character varying(20),
    apartment_no character varying(20),
    address_freeform text,
    created_at timestamp with time zone
);


--
-- Name: package_pricing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.package_pricing (
    id uuid NOT NULL,
    package_id uuid NOT NULL,
    payment_type character varying(50) NOT NULL,
    amount_monthly numeric(10,2) NOT NULL,
    currency character varying(3)
);


--
-- Name: packages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.packages (
    id uuid NOT NULL,
    package_id character varying(50) NOT NULL,
    name character varying(200) NOT NULL,
    category character varying(50) NOT NULL,
    delivery character varying(20) NOT NULL,
    platform character varying(100),
    team_required boolean,
    teams_supported json,
    notes json,
    is_active boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: sms_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sms_logs (
    id uuid NOT NULL,
    application_id uuid NOT NULL,
    to_phone character varying(20) NOT NULL,
    template character varying(100),
    message_body text,
    status character varying(20),
    sent_at timestamp with time zone
);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
001
\.


--
-- Data for Name: applications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.applications (id, customer_id, package_id, team, payment_type, delivery, status, apply_token, apply_url, token_expires_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: call_sessions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.call_sessions (id, twilio_call_sid, customer_id, application_id, caller_phone, state_history, conversation_summary, flags, started_at, ended_at, status) FROM stdin;
dfdc2358-73f5-4c28-a0c9-5b76fb6b96dc	browser-20260305223245	\N	\N	browser-test	[]	\N	[]	2026-03-06 01:32:45.293969+03	\N	active
3651e96c-1c9e-4d37-af08-cd2103475cf9	browser-20260305224338	\N	\N	browser-test	[]	\N	[]	2026-03-06 01:43:38.066753+03	\N	active
790cd004-3189-40fe-af12-305fccc9ae38	browser-20260305225012	\N	\N	browser-test	[]	\N	[]	2026-03-06 01:50:12.23065+03	\N	active
29f496ef-e365-4b2c-9d1a-8b1d93146f5c	browser-20260305225328	\N	\N	browser-test	[]	\N	[]	2026-03-06 01:53:28.954927+03	\N	active
63e2b336-da02-4264-b477-d45bbf85e850	browser-20260305225611	\N	\N	browser-test	[]	\N	[]	2026-03-06 01:56:11.48078+03	\N	active
dd157233-2062-4314-8fdc-77d810433904	browser-20260305230037	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:00:37.614513+03	\N	active
714b6619-72ad-4951-9b19-93e6cb1073c6	browser-20260305230213	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:02:13.560272+03	\N	active
4a7cffbc-7ccb-403b-9d11-8a074dc0c0b6	browser-20260305230219	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:02:19.863628+03	\N	active
481ac2b6-6fbc-4128-ae26-ca5f7f7dfed8	browser-20260305230235	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:02:35.931961+03	\N	active
6c1eb847-76cd-4408-891c-7689f035ceb9	browser-20260305230739	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:07:39.931969+03	\N	active
11bd82fe-cfda-4027-bdba-287d3bc2c992	browser-20260305230748	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:07:48.207365+03	\N	active
ec5ddaf2-f16d-4a3c-a9d2-d51b28ee6167	browser-20260305230958	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:09:58.378998+03	\N	active
86b1c3a3-cb16-43dc-9ef3-19df09cfdca9	browser-20260305231013	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:10:13.99633+03	\N	active
e4babf75-81c2-4500-b4d8-f987fc0e5f9e	browser-20260305231431	\N	\N	browser-test	[]	\N	[]	2026-03-06 02:14:31.43205+03	\N	active
baa7f184-0847-4aca-96be-6f972eed383c	browser-20260305231816	\N	\N	browser-test	[]		[]	2026-03-06 02:18:16.214409+03	2026-03-06 02:34:53.3385+03	active
932e4cb9-4ba3-4a61-a1f1-d98354765d8a	browser-20260306062440	\N	\N	browser-test	[]	\N	[]	2026-03-06 09:24:40.734725+03	\N	active
34804db0-264c-45af-9488-a0b890793654	browser-20260306063125	\N	\N	browser-test	[]	\N	[]	2026-03-06 09:31:25.561541+03	\N	active
42bcef26-d80f-48f1-8bac-d06af596238f	browser-20260306063713	\N	\N	browser-test	[]		[]	2026-03-06 09:37:13.247366+03	2026-03-06 10:01:25.737051+03	active
a518932e-85f3-43cc-a47c-24fd358062f5	browser-20260306063825	\N	\N	browser-test	[{"from": "GREET", "to": "INTENT"}]		[]	2026-03-06 09:38:25.117457+03	2026-03-06 10:01:26.113548+03	active
d0e11402-0e76-4735-9617-6c028c0923f1	browser-20260306063749	\N	\N	browser-test	[]		[]	2026-03-06 09:37:49.787695+03	2026-03-06 10:01:26.122485+03	active
66601732-b8fc-4ace-b3c0-53954dd65c59	browser-20260306072817	\N	\N	browser-test	[]	\N	[]	2026-03-06 10:28:17.072927+03	\N	active
5327cf5a-b141-44d4-a2e7-484a75ad870a	browser-20260306073009	\N	\N	browser-test	[]		[]	2026-03-06 10:30:09.490272+03	2026-03-06 10:30:16.765631+03	active
c38749da-e6fc-4b84-99d1-894b82bc418f	browser-20260306073031	\N	\N	browser-test	[]	\N	[]	2026-03-06 10:30:31.628792+03	\N	active
193e1c58-6f31-49d6-939a-da589e3a9111	browser-20260306075052	\N	\N	browser-test	[]	\N	[]	2026-03-06 10:50:52.428698+03	\N	active
6bbd0a20-cafd-4f1a-9ada-f704eb3926b0	browser-20260306075507	\N	\N	browser-test	[]	\N	[]	2026-03-06 10:55:07.284069+03	\N	active
b34440ce-68f6-45db-958e-db3e9cf7c59f	browser-20260306081726	\N	\N	browser-test	[]		[]	2026-03-06 11:17:26.719378+03	2026-03-06 11:17:46.522436+03	active
f762f657-f525-4875-b039-c3ce962ec163	browser-20260306081907	\N	\N	browser-test	[{"from": "GREET", "to": "INTENT"}, {"from": "INTENT", "to": "PACKAGE_DISCOVERY"}]		[]	2026-03-06 11:19:07.566687+03	2026-03-06 11:20:02.240994+03	active
60f8569e-fbc2-4232-86d4-f468b0714740	browser-20260306082132	\N	\N	browser-test	[]	\N	[]	2026-03-06 11:21:32.355938+03	\N	active
e630c049-5ae0-44f7-a738-4a8e33fbfe49	browser-20260306084724	\N	\N	browser-test	[]	\N	[]	2026-03-06 11:47:24.060911+03	\N	active
e807b1c1-0274-432d-b65b-e0b3559207ce	browser-20260306085059	\N	\N	browser-test	[]	\N	[]	2026-03-06 11:50:59.068697+03	\N	active
9e8c0f38-ac76-4f44-8d18-6fc204599179	browser-20260306080017	\N	\N	browser-test	[{"from": "GREET", "to": "INTENT"}, {"from": "INTENT", "to": "PACKAGE_DISCOVERY"}, {"from": "PACKAGE_DISCOVERY", "to": "PACKAGE_RECOMMEND"}]	Paket: Taraftar Paketi (Kutusuz); Teslimat: Kutusuz	[]	2026-03-06 11:00:17.622562+03	2026-03-06 12:00:19.812989+03	active
61d47889-700d-496a-a054-17c0671b7bb8	browser-20260306090142	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:01:42.086444+03	\N	active
2dbbf8db-8d16-4d23-95ce-a09857f1a331	browser-20260306090502	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:05:02.379161+03	\N	active
4e51bd9a-a57a-4968-8d3b-338a24317490	browser-20260306090632	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:06:32.308498+03	\N	active
d3f7b33f-4dad-46a0-9232-4a162e8cb313	browser-20260306090646	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:06:46.303079+03	\N	active
319c9369-ecc6-4554-b2b9-c72542270c49	browser-20260306090949	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:09:49.879077+03	\N	active
e54cec3f-5d4b-4be0-b902-35be643463ce	browser-20260306091022	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:10:22.563406+03	\N	active
244e9354-d3a3-4070-85de-3fdc7ce57794	browser-20260306091223	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:12:23.670104+03	\N	active
0d466e33-6c68-4921-b076-6dd973876f47	browser-20260306091428	\N	\N	browser-test	[]	\N	[]	2026-03-06 12:14:28.791485+03	\N	active
85201ba7-2fef-4939-be47-5374ce43e201	browser-20260306091447	\N	\N	browser-test	[]		[]	2026-03-06 12:14:47.713559+03	2026-03-06 12:18:17.622654+03	active
034e38ca-1b27-4faa-b217-76e7c922256c	browser-20260306092019	\N	\N	browser-test	[{"from": "GREET", "to": "INTENT"}, {"from": "INTENT", "to": "PACKAGE_DISCOVERY"}, {"from": "PACKAGE_DISCOVERY", "to": "PACKAGE_RECOMMEND"}, {"from": "PACKAGE_RECOMMEND", "to": "CONFIRM_CHOICE"}, {"from": "CONFIRM_CHOICE", "to": "COLLECT_IDENTITY"}]	Paket: Taraftar Paketi (Kutusuz); Takim: Galatasaray; Teslimat: Kutusuz; Odeme: Kredi Karti 12 Taksit	[]	2026-03-06 12:20:19.595002+03	2026-03-06 13:10:51.703994+03	active
8fa72e9b-f35e-47e8-9755-0c8dff61ea00	browser-20260307113420	\N	\N	browser-test	[]	\N	[]	2026-03-07 14:34:20.081411+03	\N	active
fe1b34ed-be69-4bca-a827-93bb4b9e8808	browser-20260307113433	\N	\N	browser-test	[]	\N	[]	2026-03-07 14:34:33.262717+03	\N	active
72cb58f4-4643-4e7e-8cb0-e6a0d3bd9eea	browser-20260307113502	\N	\N	browser-test	[]	\N	[]	2026-03-07 14:35:02.844195+03	\N	active
f90f2983-c421-4c96-b6db-21a3f22d0c81	browser-20260307123515	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:35:15.706539+03	\N	active
146831c0-d41f-4530-bebb-85be9f34be12	browser-20260307123529	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:35:29.860776+03	\N	active
b632ba50-d9aa-43ec-9b83-c3ba3f0a74c2	browser-20260307124106	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:41:06.669974+03	\N	active
537580ca-c824-4eef-9da4-474e93cea30c	browser-20260307124126	\N	\N	browser-test	[]		[]	2026-03-07 15:41:26.305651+03	2026-03-07 15:41:33.663845+03	active
12e36c2f-86a6-4a9a-8823-cae870a01183	browser-20260307124339	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:43:39.279288+03	\N	active
9fddc66e-7c40-4c3c-a580-13506088c728	browser-20260307125058	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:50:58.119318+03	\N	active
c427b8b7-eccf-4822-8f5d-afcf93bd20e5	browser-20260307125617	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:56:17.673698+03	\N	active
49e44746-a392-43f9-982e-cc2e38777454	browser-20260307125941	\N	\N	browser-test	[]	\N	[]	2026-03-07 15:59:41.827666+03	\N	active
0b73582c-e256-4125-9fac-72a4a1ec9ee6	browser-20260307130756	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:07:56.830064+03	\N	active
cd7a50d5-60ba-4fac-aa4e-57f801433691	browser-20260307130805	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:08:05.072967+03	\N	active
f8c4f463-7925-4127-b36e-0c78331be6ca	browser-20260307130947	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:09:47.557515+03	\N	active
7404b5eb-ea51-4c52-83b9-347040674bc3	browser-20260307131330	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:13:30.241424+03	\N	active
01b65034-adbc-4e8b-b4ef-0e383d16e360	browser-20260307131354	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:13:54.591332+03	\N	active
f9d43d02-29a3-475b-a4b2-b530eb5aa945	browser-20260307131404	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:14:04.096106+03	\N	active
34eaa375-1bb4-444d-a92f-0a1b2eacdbe2	browser-20260307131527	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:15:27.943504+03	\N	active
8a744a0a-1b70-4dfe-b245-00254d3b81bc	browser-20260307133008	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:30:08.757368+03	\N	active
014f4c59-f04b-4ad4-903a-3f42458f8547	browser-20260307133630	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:36:30.86448+03	\N	active
487e06b0-eb61-4e94-bf95-96127ee92ca6	browser-20260307134146	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:41:46.12562+03	\N	active
17a95c6a-fbe8-49dd-818a-960806af4e16	browser-20260307134154	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:41:54.837885+03	\N	active
f542a739-bd30-4d2b-8122-87beac45f8fd	browser-20260307134332	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:43:32.164493+03	\N	active
c1aab5b1-4626-4ecb-ae51-bc560014e022	browser-20260307135049	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:50:49.89178+03	\N	active
077d0481-fae5-4f1d-8bc3-91fe8db268f9	browser-20260307135059	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:50:59.503638+03	\N	active
e0623868-f83c-4024-88eb-c7ac3cf85e2f	browser-20260307135228	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:52:28.824926+03	\N	active
8f961cd8-94d4-4b4d-8110-9f3b8383fa38	browser-20260307135400	\N	\N	browser-test	[]	\N	[]	2026-03-07 16:54:00.76586+03	\N	active
88ebed09-f866-40e9-941b-b5a633673d58	browser-20260307140230	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:02:30.555902+03	\N	active
bf5b5499-03ff-421a-9d97-9773d5309b6d	browser-20260307140324	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:03:24.745756+03	\N	active
a800ff7f-a9f5-4f7f-bc09-9d51f883738d	browser-20260307140334	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:03:34.813646+03	\N	active
7c5fe44a-b8bc-4e47-b0de-cad94ebfe2f5	browser-20260307140346	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:03:46.740711+03	\N	active
e430d000-1d1c-428e-b530-ff89e49dda76	browser-20260307140847	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:08:47.280396+03	\N	active
8e953634-74e6-4444-ba78-b628fce8d981	browser-20260307140941	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:09:41.305438+03	\N	active
36ced853-dd70-4e20-bd64-e34a02bae88c	browser-20260307140951	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:09:51.532904+03	\N	active
8e871338-407f-4f2e-80f7-2f798f92f141	browser-20260307141150	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:11:50.627618+03	\N	active
f38c2a81-c3f1-4e1d-9460-a3e62108e9fd	browser-20260307141302	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:13:02.46512+03	\N	active
504e76d8-f81b-49e3-bd43-1f30bd43723d	browser-20260307141333	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:13:33.181+03	\N	active
b917cde4-817a-424e-ac25-5bc6ee0c151a	browser-20260307141510	\N	\N	browser-test	[]	\N	[]	2026-03-07 17:15:10.854588+03	\N	active
b5afd8fd-e2af-4cc4-9498-f99caa2c279e	browser-20260307142206	\N	\N	browser-test	[]	TCKN: ***1666	[]	2026-03-07 17:22:06.266329+03	2026-03-07 18:22:08.30589+03	active
e1313663-4ebd-4085-bb6b-459b15db6f9c	browser-20260309071519	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:15:19.471004+03	\N	active
32d0c7c4-6c4b-4ca1-9494-4f1c75753ed3	browser-20260309071530	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:15:30.145805+03	\N	active
f158f08a-e76b-4bdd-a31e-5971feb02a99	browser-20260309071539	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:15:39.342166+03	\N	active
7897d4a9-bebc-4328-ba2e-9c042d75c1cf	browser-20260309071624	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:16:24.106956+03	\N	active
f34f6f31-7b16-4d3e-8bf2-4952bf382a66	browser-20260309071642	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:16:42.142724+03	\N	active
902967d6-97d7-4803-9f62-b120a28a1a31	browser-20260309072451	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:24:51.942159+03	\N	active
3ed6b76f-8b62-4e0a-9302-0cb9e6492f05	browser-20260309073522	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:35:22.024021+03	\N	active
c29aa0a0-64b0-4518-b092-f694a1d0050d	browser-20260309073748	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:37:48.201222+03	\N	active
b9248473-9eba-4817-92d1-252ba2dadc60	browser-20260309073758	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:37:58.439883+03	\N	active
fbba2ef8-bdf3-4336-ada1-e504c774870f	browser-20260309073843	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:38:43.580755+03	\N	active
572d34f3-8d19-45e1-809a-b6c3a1c30c30	browser-20260309073922	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:39:22.19093+03	\N	active
0b7549b4-07cd-42fe-a8bc-b14365e15988	browser-20260309073941	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:39:41.44802+03	\N	active
cf85dfe7-c913-4ab9-aef4-9397b4cf4c3f	browser-20260309073958	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:39:58.663457+03	\N	active
1b1527c5-c003-4189-bdb9-d68cffac5c06	browser-20260309074007	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:40:07.137351+03	\N	active
e874b534-0b31-40f9-9cbd-16c2f083a5a4	browser-20260309074014	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:40:14.223023+03	\N	active
52504331-3e57-40d5-a337-280a0086e5c8	browser-20260309074339	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:43:39.321345+03	\N	active
c25bc12f-c9f4-49f9-a180-efaf8ddabf6b	browser-20260309074416	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:44:16.147236+03	\N	active
e2d12c57-51ad-41d0-bef4-4abd6dfa64b2	browser-20260309075301	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:53:01.025859+03	\N	active
0a0c564f-e16d-408d-912e-49c148ab77f3	browser-20260309075353	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:53:53.943164+03	\N	active
ee871a74-0bf0-4ee5-80f0-f98459372cae	browser-20260309075446	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:54:46.699139+03	\N	active
fca58e05-bf48-4d75-805f-4f139c6fc63f	browser-20260309075501	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:55:01.372901+03	\N	active
5dfbcf69-2e7d-4777-bb92-2c80d5097501	browser-20260309075514	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:55:14.232648+03	\N	active
a20ba149-5f73-450c-9fdd-5ccde6e94110	browser-20260309075624	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:56:24.852573+03	\N	active
e9a703b7-c4fc-4baa-a5d2-471acf7c9472	browser-20260309075640	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:56:40.749579+03	\N	active
0cc90b00-8b6b-414c-ab75-59b88ea4eac3	browser-20260309075754	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:57:54.880602+03	\N	active
d851783b-41ed-4cc1-90e6-9902d2bff8b2	browser-20260309075813	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:58:13.493106+03	\N	active
abb1f7e6-f6ff-4ecf-aa1e-306e27fa2ba9	browser-20260309075901	\N	\N	browser-test	[]	\N	[]	2026-03-09 10:59:01.62842+03	\N	active
a227cb11-0cb3-4ed2-a164-4dd41e0796d6	browser-20260309080212	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:02:12.211064+03	\N	active
800f3e32-6560-46fb-90b9-bf594d9867b0	browser-20260309080432	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:04:32.464553+03	\N	active
9a63f53d-4ef5-4934-9fc4-e018cfc0e60c	browser-20260309080440	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:04:40.277428+03	\N	active
70b57cad-d741-498c-a6f6-e9feadb45f03	browser-20260309081200	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:12:00.427216+03	\N	active
9fdac682-d42b-43cc-b09e-86e0e784dc51	browser-20260309081738	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:17:38.905833+03	\N	active
9506b5b1-3c43-4216-91d7-46a3dd0810eb	browser-20260309081745	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:17:45.915737+03	\N	active
ab98980d-d1b5-477b-a837-43b5a9bbb58e	browser-20260309081801	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:18:01.187248+03	\N	active
ab96530a-f11b-45bb-8289-e71df72c1815	browser-20260309082207	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:22:07.963089+03	\N	active
4a112164-3179-48fe-8bf7-c5609217113f	browser-20260309082330	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:23:30.464934+03	\N	active
a2ba6a9b-dbeb-49f8-8367-26289c4e0b9e	browser-20260309082639	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:26:39.499667+03	\N	active
c94b8b54-15ae-4446-b8b1-2eecd154c8c3	browser-20260309082652	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:26:52.563456+03	\N	active
a4d1557d-6275-4f5a-9b65-da3c9ea68b6c	browser-20260309082853	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:28:53.048375+03	\N	active
5bd09d8f-abcd-4992-b30c-1d02d93be5b6	browser-20260309082900	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:29:00.573541+03	\N	active
0ee22311-f06c-415a-9e21-15ce6792b93b	browser-20260309082914	\N	\N	browser-test	[]	\N	[]	2026-03-09 11:29:14.858373+03	\N	active
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.customers (id, name, surname, tckn, birth_date, phone, city, district, neighborhood, street, building_no, apartment_no, address_freeform, created_at) FROM stdin;
\.


--
-- Data for Name: package_pricing; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.package_pricing (id, package_id, payment_type, amount_monthly, currency) FROM stdin;
c85dcc71-2951-478f-9eab-62aa05c04473	df093c76-dc58-4879-8d01-b70ea70ed358	credit_card_installment_12	449.00	TRY
7155c5c1-3748-4a4f-ac7e-3c81d31f6277	7e5202f6-4a89-4d09-8e64-8d9bb299c614	credit_card_installment_12	549.00	TRY
1eb32d8c-602e-446c-b559-643e320f2129	7e5202f6-4a89-4d09-8e64-8d9bb299c614	invoiced	669.00	TRY
430ad368-617a-49d4-9503-34df6b162865	a98f5bf6-c1cb-4e8d-8083-db415ac885c9	credit_card_installment_12	569.00	TRY
0aa94df0-1eec-4167-97a7-e4f0ffe92a7d	f2946f64-13dc-4e44-a999-b9c607a5fafa	credit_card_installment_12	549.00	TRY
a590c5ca-c5bf-4c50-963c-ad2c9a2d6406	f2946f64-13dc-4e44-a999-b9c607a5fafa	invoiced	689.00	TRY
dd423cb4-0837-42a8-8022-04bdb190e5a7	1834b120-4c28-4443-bc5a-31bd7f26cb2f	monthly	599.00	TRY
c6d5b39d-7c66-47f6-86d0-d23273389112	40698881-76d8-423f-af94-98947fdaf1b4	monthly	659.00	TRY
a9ba1fe8-0880-45aa-b3a9-2be2a6b5ef54	f5787ed5-0ee8-41f1-97e0-59cf692336ed	monthly	999.00	TRY
\.


--
-- Data for Name: packages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.packages (id, package_id, name, category, delivery, platform, team_required, teams_supported, notes, is_active, created_at, updated_at) FROM stdin;
df093c76-dc58-4879-8d01-b70ea70ed358	FAN_UNBOXED	Taraftar Paketi (Kutusuz)	kampanyali_paketler	kutusuz	beIN CONNECT	t	["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor"]	["beIN CONNECT ile aninda izleyin", "Kredi kartli odeme"]	t	2026-03-06 00:12:11.625544+03	2026-03-06 00:12:11.625544+03
7e5202f6-4a89-4d09-8e64-8d9bb299c614	FAN_BOXED	Taraftar Paketi (Kutulu)	kutulu_paketler	kutulu	kutu + kurulum	t	["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor"]	["beIN CONNECT ile aninda izleyin", "Faturali veya Kredi Kartli odeme"]	t	2026-03-06 00:12:11.629976+03	2026-03-06 00:12:11.629976+03
a98f5bf6-c1cb-4e8d-8083-db415ac885c9	SPORTSTAR_UNBOXED	Sporun Yildizi (Kutusuz)	kampanyali_paketler	kutusuz	beIN CONNECT	f	[]	["beIN CONNECT ile aninda izleyin", "Kredi kartli odeme"]	t	2026-03-06 00:12:11.638171+03	2026-03-06 00:12:11.638171+03
f2946f64-13dc-4e44-a999-b9c607a5fafa	SPORTSTAR_BOXED_PRIORITY_PROVINCES	Sporun Yildizi (Kutulu) - Kalkinmada Oncelikli Illere Ozel	kampanyali_paketler	kutulu	kutu + kurulum	f	[]	["beIN CONNECT ile aninda izleyin", "Faturali veya Kredi Kartli odeme"]	t	2026-03-06 00:12:11.641172+03	2026-03-06 00:12:11.641172+03
1834b120-4c28-4443-bc5a-31bd7f26cb2f	NET_ENT_FAN_UNBOXED	Internet + Eglence + Taraftar (Kutusuz)	internet_paketleri	kutusuz	Digiturk Internet + beIN CONNECT	f	[]	["Digiturk Internet ve beIN CONNECT bir arada", "6 ay tum kanallar hediye"]	t	2026-03-06 00:12:11.645258+03	2026-03-06 00:12:11.645258+03
40698881-76d8-423f-af94-98947fdaf1b4	NET_ENT_FAN_BOXED	Internet + Eglence + Taraftar (Kutulu)	internet_paketleri	kutulu	Digiturk Internet + kutu + kurulum	f	[]	["Limitsiz internet, Film, Dizi, Avrupa Ligleri", "12 ay taraftar paketi hediye"]	t	2026-03-06 00:12:11.647781+03	2026-03-06 00:12:11.647781+03
f5787ed5-0ee8-41f1-97e0-59cf692336ed	NET_ENT_SPORTSTAR_UNBOXED	Internet + Eglence + Sporun Yildizi (Kutusuz)	internet_paketleri	kutusuz	Digiturk Internet + beIN CONNECT	f	[]	["Limitsiz internet, Film, Dizi, Avrupa Ligleri", "12 ay taraftar paketi hediye"]	t	2026-03-06 00:12:11.647781+03	2026-03-06 00:12:11.647781+03
\.


--
-- Data for Name: sms_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sms_logs (id, application_id, to_phone, template, message_body, status, sent_at) FROM stdin;
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: call_sessions call_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_sessions
    ADD CONSTRAINT call_sessions_pkey PRIMARY KEY (id);


--
-- Name: call_sessions call_sessions_twilio_call_sid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_sessions
    ADD CONSTRAINT call_sessions_twilio_call_sid_key UNIQUE (twilio_call_sid);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: package_pricing package_pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.package_pricing
    ADD CONSTRAINT package_pricing_pkey PRIMARY KEY (id);


--
-- Name: packages packages_package_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.packages
    ADD CONSTRAINT packages_package_id_key UNIQUE (package_id);


--
-- Name: packages packages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.packages
    ADD CONSTRAINT packages_pkey PRIMARY KEY (id);


--
-- Name: sms_logs sms_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sms_logs
    ADD CONSTRAINT sms_logs_pkey PRIMARY KEY (id);


--
-- Name: ix_call_sessions_twilio_call_sid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_call_sessions_twilio_call_sid ON public.call_sessions USING btree (twilio_call_sid);


--
-- Name: ix_packages_package_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_packages_package_id ON public.packages USING btree (package_id);


--
-- Name: applications applications_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: applications applications_package_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_package_id_fkey FOREIGN KEY (package_id) REFERENCES public.packages(id);


--
-- Name: call_sessions call_sessions_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_sessions
    ADD CONSTRAINT call_sessions_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id);


--
-- Name: call_sessions call_sessions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.call_sessions
    ADD CONSTRAINT call_sessions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: package_pricing package_pricing_package_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.package_pricing
    ADD CONSTRAINT package_pricing_package_id_fkey FOREIGN KEY (package_id) REFERENCES public.packages(id) ON DELETE CASCADE;


--
-- Name: sms_logs sms_logs_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sms_logs
    ADD CONSTRAINT sms_logs_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id);


--
-- PostgreSQL database dump complete
--

